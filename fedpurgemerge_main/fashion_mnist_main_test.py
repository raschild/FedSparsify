from simulatedFL.models.model import Model
from simulatedFL.models.fashion_mnist_fc import FashionMnistModel
from simulatedFL.utils.model_state import ModelState
from simulatedFL.utils.model_training import ModelTraining
from simulatedFL.utils.data_distribution import PartitioningScheme
from tensorflow.keras.regularizers import l2
from tensorflow.keras.regularizers import l1

import os
import json
import random
import numpy as np
import tensorflow as tf

import simulatedFL.utils.model_merge as merge_ops
import simulatedFL.utils.model_purge as purge_ops

os.environ['CUDA_VISIBLE_DEVICES'] = "0"
np.random.seed(1990)
random.seed(1990)
tf.random.set_seed(1990)


if __name__ == "__main__":

	gpus = tf.config.experimental.list_physical_devices("GPU")
	if gpus:
		try:
			for gpu in gpus:
				# tf.config.experimental.set_memory_growth(gpu, False)
				tf.config.experimental.set_virtual_device_configuration(
					gpu, [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=4096)],) # 4GBs
		except RuntimeError as e:
			# Visible devices must be set before GPUs have been initialized
			print(e)

	""" Model Definition. """
	lambda1 = l1(0.0001)
	lambda2 = l2(0.0001)

	model = FashionMnistModel(kernel_initializer=Model.InitializationStates.GLOROT_UNIFORM, learning_rate=0.02,
							  kernel_regularizer=None, bias_regularizer=None).get_model
	model().summary()

	""" Load the data. """
	(x_train, y_train), (x_test, y_test) = tf.keras.datasets.fashion_mnist.load_data()
	x_train = (x_train.astype('float32') / 256).reshape(-1, 28, 28, 1)
	x_test = (x_test.astype('float32') / 256).reshape(-1, 28, 28, 1)

	output_logs_dir = os.path.dirname(__file__) + "/../logs/FashionMNIST/"
	output_npzarrays_dir = os.path.dirname(__file__) + "/../npzarrays/FashionMNIST/"

	experiment_template = \
		"FedAvg.NonIID.rounds_{}.learners_{}.participation_{}.le_{}.compression_{}.sparsificationround_{}.sparsifyevery_{}rounds.finetuning_{}"
	# experiment_template = \
	# 	"FashionMNIST.rounds_{}.learners_{}.participation_{}.le_{}.compression_{}.sparsificationround_{}.finetuning_{}"

	rounds_num = 200
	learners_num_list = [10, 100]
	participation_rates_list = [1, 0.1]
	# participation_rates_list = [1, 0.5, 0.1]

	# One-Shot Pruning
	# sparsity_levels = [0.0, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]
	# sparsity_levels = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]
	# start_sparsification_at_round = [1, 5, 10, 90]

	# Centralized Progressive Pruning
	# sparsity_levels = [0.005, 0.01, 0.02]
	# start_sparsification_at_round = [1, 25, 50]
	start_sparsification_at_round = [1]

	# Federated Progressive Pruning
	# sparsity_levels = [0.005, 0.01, 0.02]
	# start_sparsification_at_round = [0, 25]
	# sparsity_levels = [0.7, 0.8, 0.9]
	# sparsity_levels = [0.01, 0.02, 0.04]
	sparsity_levels = [0.01, 0.02, 0.04]
	sparsification_frequency = [1, 2, 4]

	local_epochs = 4
	fine_tuning_epochs = [0]
	batch_size = 32
	train_with_global_mask = True

	for learners_num, participation_rate  in zip(learners_num_list, participation_rates_list):
		for sparsity_level in sparsity_levels:
			for frequency in sparsification_frequency:
				for sparsification_round in start_sparsification_at_round:
					for fine_tuning_epoch_num in fine_tuning_epochs:

						# fill in string placeholders
						filled_in_template = experiment_template.format(rounds_num,
																		learners_num,
																		str(participation_rate).replace(".", ""),
																		str(local_epochs),
																		str(sparsity_level).replace(".", ""),
																		str(sparsification_round),
																		str(frequency),
																		fine_tuning_epoch_num)
						output_arrays_dir = output_npzarrays_dir + filled_in_template

						pscheme = PartitioningScheme(x_train=x_train, y_train=y_train, partitions_num=learners_num)
						# x_chunks, y_chunks = pscheme.iid_partition()
						x_chunks, y_chunks = pscheme.non_iid_partition(classes_per_partition=2)

						scaling_factors = [y_chunk.size for y_chunk in y_chunks]

						# Merging Ops.
						merge_op = merge_ops.MergeWeightedAverage(scaling_factors)
						# merge_op = merge_ops.MergeMedian(scaling_factors)
						# merge_op = merge_ops.MergeAbsMax(scaling_factors)
						# merge_op = merge_ops.MergeAbsMin(scaling_factors, discard_zeroes=True)
						# merge_op = merge_ops.MergeTanh(scaling_factors)
						# merge_op = merge_ops.MergeWeightedAverageNNZ(scaling_factors)
						# merge_op = merge_ops.MergeWeightedAverageMajorityVoting(scaling_factors)

						# Purging Ops.
						# purge_op = purge_ops.PurgeByWeightMagnitude(sparsity_level=sparsity_level)
						purge_op = purge_ops.PurgeByNNZWeightMagnitude(sparsity_level=sparsity_level,
																	   sparsify_every_k_round=frequency)
						# purge_op = purge_ops.PurgeByNNZWeightMagnitudeRandom(sparsity_level=sparsity_level,
						# 													 num_params=model().count_params(),
						# 													 sparsify_every_k_round=frequency)
						# purge_op = purge_ops.PurgeByLayerWeightMagnitude(sparsity_level=sparsity_level)
						# purge_op = purge_ops.PurgeByLayerNNZWeightMagnitude(sparsity_level=sparsity_level)
						# purge_op = purge_ops.PurgeByWeightMagnitudeGradual(start_at_round=0,
						# 												   sparsity_level_init=0.5,
						# 												   sparsity_level_final=0.85,
						# 												   total_rounds=rounds_num,
						# 												   delta_round_pruning=1)
						# sparsity_level = purge_op.to_json()
						# randint = random.randint(0, learners_num-1)
						# purge_op = purge_ops.PurgeSNIP(model(),
						# 							   sparsity=sparsity_level,
						# 							   x=x_chunks[randint][:batch_size],
						# 							   y=y_chunks[randint][:batch_size])
						# randint = random.randint(0, learners_num-1)
						# purge_op = purge_ops.PurgeGrasp(model(),
						# 							   sparsity=sparsity_level,
						# 							   x=x_chunks[randint][:batch_size],
						# 							   y=y_chunks[randint][:batch_size])

						federated_training = ModelTraining.FederatedTraining(merge_op=merge_op,
																			 learners_num=learners_num,
																			 rounds_num=rounds_num,
																			 local_epochs=local_epochs,
																			 learners_scaling_factors=scaling_factors,
																			 participation_rate=participation_rate,
																			 batch_size=batch_size,
																			 purge_op_local=purge_op,
																			 purge_op_global=None,
																			 start_purging_at_round=sparsification_round,
																			 fine_tuning_epochs=fine_tuning_epoch_num,
																			 train_with_global_mask=train_with_global_mask,
																			 start_training_with_global_mask_at_round=sparsification_round,
																			 output_arrays_dir=output_arrays_dir)
																			 # precomputed_masks=purge_op.precomputed_masks)
						federated_training.execution_stats['federated_environment']['model_params'] = ModelState.count_non_zero_elems(model())
						federated_training.execution_stats['federated_environment']['sparsity_level'] = sparsity_level
						federated_training.execution_stats['federated_environment']['additional_specs'] = purge_op.json()
						federated_training.execution_stats['federated_environment']['data_distribution'] = \
							pscheme.to_json_representation()
						print(federated_training.execution_stats)
						federated_training_results = federated_training.start(get_model_fn=model, x_train_chunks=x_chunks,
																			  y_train_chunks=y_chunks, x_test=x_test,
																			  y_test=y_test, info="Fashion-MNIST")

						execution_output_filename = output_logs_dir + filled_in_template + ".json"
						with open(execution_output_filename, "w+", encoding='utf-8') as fout:
							json.dump(federated_training_results, fout, ensure_ascii=False, indent=4)
