#-*-coding:utf-8-*-
import tensorflow as tf
import tensorflow.contrib.slim as slim
from train_config import config as cfg



def block(x, num_units,out_channels=None, scope='stage'):
    with tf.variable_scope(scope):

        with tf.variable_scope('unit_1'):
            x, y = basic_unit_with_downsampling(x,out_channels)

        for j in range(2, num_units + 1):
            with tf.variable_scope('unit_%d' % j):
                x, y = concat_shuffle_split(x, y)

                x = basic_unit(x)

        x = tf.concat([x, y], axis=3)

    return x

def concat_shuffle_split(x, y):
    with tf.name_scope('concat_shuffle_split'):
        shape = tf.shape(x)
        batch_size = shape[0]
        height, width = shape[1], shape[2]

        depth = x.shape[3].value

        z = tf.concat([x, y], axis=3)  # shape [batch_size, height, width, 2, depth]
        z = tf.reshape(z, [batch_size, height, width, 2,depth])
        z = tf.transpose(z, [0, 1, 2, 4, 3])
        z = tf.reshape(z, [batch_size, height, width, 2*depth])
        x, y = tf.split(z, num_or_size_splits=2, axis=3)
        return x, y

def basic_unit(x):
    in_channels = x.shape[3].value

    x = slim.conv2d(x, in_channels, [1, 1], stride=1, activation_fn=tf.nn.relu,
                normalizer_fn=slim.batch_norm, scope='conv1x1_before')

    x = slim.separable_conv2d(x, num_outputs=None, kernel_size=[3, 3], stride=1, activation_fn=None,
                              normalizer_fn=slim.batch_norm, scope='depthwise', depth_multiplier=1)

    x = slim.conv2d(x, in_channels, [1, 1], stride=1, activation_fn=tf.nn.relu,
                    normalizer_fn=slim.batch_norm, scope='conv1x1_after')
    return x

def basic_unit_with_downsampling(x,out_channels=None):
    in_channels = x.shape[3].value
    out_channels = 2 * in_channels if out_channels is None else out_channels

    y = slim.conv2d(x, in_channels, [1, 1], stride=1, activation_fn=tf.nn.relu,
                      normalizer_fn=slim.batch_norm, scope='conv1x1_before')

    y = slim.separable_conv2d(y, num_outputs=None, kernel_size=[3, 3], stride=2, activation_fn=None,
                    normalizer_fn=slim.batch_norm, scope='depthwise',depth_multiplier=1)

    y = slim.conv2d(y, out_channels//2, [1, 1], stride=1, activation_fn=tf.nn.relu,
                    normalizer_fn=slim.batch_norm, scope='conv1x1_after')

    with tf.variable_scope('second_branch'):
        x = slim.separable_conv2d(x, num_outputs=None, kernel_size=[3, 3], stride=2, activation_fn=None,
                                  normalizer_fn=slim.batch_norm, scope='depthwise',depth_multiplier=1)
        x = slim.conv2d(x, out_channels // 2, [1, 1], stride=1, activation_fn=tf.nn.relu,
                        normalizer_fn=slim.batch_norm, scope='conv1x1_after')

    return x, y


def shufflenet_arg_scope(weight_decay=cfg.TRAIN.weight_decay_factor,
                     batch_norm_decay=0.997,
                     batch_norm_epsilon=1e-5,
                     batch_norm_scale=True,
                     use_batch_norm=True,
                     batch_norm_updates_collections=tf.GraphKeys.UPDATE_OPS):
  """Defines the default ResNet arg scope.
  TODO(gpapan): The batch-normalization related default values above are
    appropriate for use in conjunction with the reference ResNet models
    released at https://github.com/KaimingHe/deep-residual-networks. When
    training ResNets from scratch, they might need to be tuned.
  Args:
    weight_decay: The weight decay to use for regularizing the model.
    batch_norm_decay: The moving average decay when estimating layer activation
      statistics in batch normalization.
    batch_norm_epsilon: Small constant to prevent division by zero when
      normalizing activations by their variance in batch normalization.
    batch_norm_scale: If True, uses an explicit `gamma` multiplier to scale the
      activations in the batch normalization layer.
    activation_fn: The activation function which is used in ResNet.
    use_batch_norm: Whether or not to use batch normalization.
    batch_norm_updates_collections: Collection for the update ops for
      batch norm.
  Returns:
    An `arg_scope` to use for the resnet models.
  """
  batch_norm_params = {
      'decay': batch_norm_decay,
      'epsilon': batch_norm_epsilon,
      'scale': batch_norm_scale,
      'updates_collections': batch_norm_updates_collections,
      'fused': True,  # Use fused batch norm if possible.
  }

  with slim.arg_scope(
      [slim.conv2d,slim.separable_conv2d],
      weights_regularizer=slim.l2_regularizer(weight_decay),
      weights_initializer=slim.variance_scaling_initializer(),
      biases_initializer=None,
      normalizer_fn=slim.batch_norm if use_batch_norm else None,
      normalizer_params=batch_norm_params):
    with slim.arg_scope([slim.batch_norm], **batch_norm_params):
      # The following implies padding='SAME' for pool1, which makes feature
      # alignment easier for dense prediction tasks. This is also used in
      # https://github.com/facebook/fb.resnet.torch. However the accompanying
      # code of 'Deep Residual Learning for Image Recognition' uses
      # padding='VALID' for pool1. You can switch to that choice by setting
      # slim.arg_scope([slim.max_pool2d], padding='VALID').
      with slim.arg_scope([slim.max_pool2d], padding='SAME') as arg_sc:
        return arg_sc




def cpm(product,scope,dim):
    with tf.variable_scope(scope):
        # eyes_1 = slim.separable_conv2d(product, dim // 2, [1, 1], stride=1, rate=1, activation_fn=tf.nn.relu,
        #                      scope='eyes_1')

        eyes_2 = slim.separable_conv2d(product, dim // 8, [3, 3], stride=1, rate=2, activation_fn=tf.nn.relu,
                             scope='eyes_2')

        eyes_3 = slim.separable_conv2d(eyes_2, dim // 8, [3, 3], stride=1, rate=2, activation_fn=tf.nn.relu,
                             scope='eyes_3')

    fme_res = tf.concat([product, eyes_2, eyes_3], axis=3)

    return fme_res



def create_fpn_net(blocks,dims_list):

    of1, of2, of3= blocks

    lateral2 = slim.conv2d(of2, dims_list[1], [1, 1],
                          padding='SAME',
                          scope='lateral/res{}'.format(2))

    upsample2_of3 = slim.conv2d(of3, dims_list[1], [1, 1],
                           padding='SAME',
                           scope='merge/res{}'.format(2))
    upsample2 = tf.keras.layers.UpSampling2D(data_format='channels_last' )(upsample2_of3)

    fem_2 = lateral2 + upsample2

    lateral1 = slim.conv2d(of1, dims_list[0], [1, 1],
                           padding='SAME',
                           scope='lateral/res{}'.format(1))

    upsample1_of2 = slim.conv2d(fem_2, dims_list[0], [1, 1],
                            padding='SAME',
                            scope='merge/res{}'.format(1))
    upsample1 = tf.keras.layers.UpSampling2D(data_format='channels_last')(upsample1_of2)

    #fem_1 = lateral1 + upsample1
    fem_1 = lateral1+upsample1
    #####enhance model
    fpn_fms = [fem_1, fem_2, of3]

    return fpn_fms

def shufflenet_v2_ssd(inputs,is_training=True,depth_multiplier='0.5'):
    possibilities = {'0.5': 48,'0.75':64, '1.0': 116, '1.5': 176, '2.0': 224}
    initial_depth = possibilities[depth_multiplier]

    arg_scope = shufflenet_arg_scope()
    with slim.arg_scope(arg_scope):
        with slim.arg_scope([slim.batch_norm], is_training=is_training):
            with tf.variable_scope('ShuffleNetV2'):

                net = slim.conv2d(inputs, 8, [3, 3],stride=2, activation_fn=tf.nn.relu,
                                  normalizer_fn=slim.batch_norm, scope='init_conv')

                net = slim.separable_conv2d(net, 12, [3, 3], stride=2, activation_fn=tf.nn.relu,
                                          normalizer_fn=slim.batch_norm, scope='init_conv_2', depth_multiplier=1)


                block1 = block(net, num_units=4, out_channels=initial_depth, scope='Stage2')

                block2 = block(block1, num_units=8, out_channels=initial_depth*2, scope='Stage3')

                block3 = block(block2, num_units=4, out_channels=initial_depth*2, scope='Stage4')

            fms=[block1,block2,block3]

            if cfg.MODEL.fpn:
                with tf.variable_scope('fpn'):
                    fms=create_fpn_net(fms,dims_list=cfg.MODEL.fpn_dims)

    return fms




