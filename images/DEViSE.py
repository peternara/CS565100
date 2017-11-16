from __future__ import division, print_function, absolute_import
import numpy as np
import tensorflow as tf
import os
import tflearn

# Data loading
from tflearn.datasets import cifar100
(X, Y), (testX, testY) = cifar100.load_data()
# divided into validation set, training set
total = X.shape[0]
X_train = X[:int(total*0.8),:,:,:]
Y_train = Y[:int(total*0.8)]
X_valid = X[int(total*0.8):,:,:,:]
Y_valid = Y[int(total*0.8):]

X_impred_train = np.load('X_impred_train.npy')
X_impred_valid = np.load('X_impred_valid.npy')
testX_impred = np.load('testX_impred.npy')
Y_train_vec = np.load('Y_train_vec.npy')
Y_valid_vec = np.load('Y_valid_vec.npy')
testY_vec = np.load('testY_vec.npy')

fine_label = np.load('fine_label_vec.npy')


### Environment settings###
# Setting Parameters
logs_path = 'TensorBoard/'
n_features = 4096 # number of image pixels 
batch_size = 100 # Size of a mini-batch

# Launching InteractiveSession
sess = tf.InteractiveSession()
with tf.name_scope('Input'):
    x = tf.placeholder(tf.float32, shape=[None, 8, 8, 64])
with tf.name_scope('Label'):
    y_ = tf.placeholder(tf.int32, shape=[None, 500])

# Defining weight and bias variables
def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)
def bias_variable(shape):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial)


### Build DEViSE model
with tf.name_scope('M'):
    W_fc1 = weight_variable([4096, 500]) 
    b_fc1 = bias_variable([500])
    x_image_flat = tf.reshape(x, [-1, 4096])
    y_conv = tf.nn.relu(tf.matmul(x_image_flat, W_fc1) + b_fc1)
### Similarity


#calculate the inner product with each fine label
def similarity(result, fine):
    near_tmp = tf.matmul(tf.constant(fine, dtype='float32'), tf.transpose(result))
    nearest = tf.argmax(near_tmp, axis=0, output_type=tf.int32)
    return nearest


with tf.name_scope('similarity'):
    nearest = similarity(y_conv, fine_label)

# Regression
with tf.name_scope('hinge_loss'):
    hinge_loss = tf.losses.hinge_loss(labels=y_, logits=y_conv)
    tf.summary.scalar("hinge_loss", hinge_loss)
train_step = tf.train.AdamOptimizer(1e-4).minimize(hinge_loss)

#Calculating the average loss of the model
with tf.name_scope('avg_loss'):
    avg_loss = tf.reduce_mean(tf.cast(hinge_loss, tf.float32))
    tf.summary.scalar("avg_loss", avg_loss)
# Calculating the accuracy of the model

y_label_idx = tf.placeholder(tf.int32, shape=[None])
correct_prediction = tf.equal(nearest, y_label_idx)

with tf.name_scope('Accuracy'):
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
    tf.summary.scalar("Accuracy", accuracy)

# Saving checkpoints
saver = tf.train.Saver()
save_dir = 'checkpoints/'
if not os.path.exists(save_dir):
    os.makedirs(save_dir)
save_path = os.path.join(save_dir, 'best_validation')

# Session initialization
sess.run(tf.global_variables_initializer())
tf.contrib.layers.variance_scaling_initializer(factor=1.0, mode='FAN_AVG', uniform=False)

# Output visualized graph
merged = tf.summary.merge_all()
writer = tf.summary.FileWriter(logs_path, graph = tf.get_default_graph())

#calculate the inner product with each fine label
def similarity(result, fine):
    label_num = fine.shape[0]
    for i in range(label_num):
        near_tmp[i] = np.linalg.norm(result - fine[i])
    nearest = np.argmax(near_tmp)
    return nearest

# Defining a function to create a mini-batch
def next_batch(num, data, labels, labels_idx):
    '''
    Return a total of `num` random samples and labels. 
    '''
    idx = np.arange(0 , len(data))
    np.random.shuffle(idx)
    idx = idx[:num]
    data_shuffle = [data[ i] for i in idx]
    labels_shuffle = [labels[ i] for i in idx]
    labels_idx_shuffle = [labels_idx[ i] for i in idx]

    return np.asarray(data_shuffle), np.asarray(labels_shuffle), np.asarray(labels_idx_shuffle)

# Function for calculation the accuracy of validation set    
def validation_accuracy(batch_size, images, labels, labels_idx):
    num_images = len(images)
    cls_pred = 0
    i = 0
    num_batch = 0
    while i < num_images:
        j = min(i + batch_size, num_images)    # j means the first id of next batch of validation set
        feed_dict = {x: images[i:j], y_: labels[i:j], y_label_idx: labels_idx[i:j]}     # creating feed dict. to run the model for computing accuracy
        cls_pred = cls_pred + (sess.run(accuracy, feed_dict=feed_dict))*(j-i)    # predicting the answer to the validation input
        i = j

    acc = cls_pred / num_images     # computing the accuracy
    return acc

# Function for calculation the accuracy of validation set    
def validation_accuracy(batch_size, images, labels):
    num_images = len(images)
    cls_pred = np.zeros(shape=num_images, dtype=np.int)
    i = 0
    while i < num_images:
        j = min(i + batch_size, num_images)    # j means the first id of next batch of validation set
        feed_dict = {x: images[i:j, :], y_: labels[i:j]}     # creating feed dict. to run the model for computing accuracy
        cls_pred[i:j] = sess.run(tf.argmax(nearest, axis=1, output_type=tf.int32), feed_dict=feed_dict)    # predicting the answer to the validation input
        i = j
    correct = (labels == cls_pred)    # if predicted values (cls_pred) is identical to answers (labels), then set "True" in the corresponding elements of "correct" list.
    acc = float(correct.sum()) / len(correct)     # computing the accuracy
    return acc

# Initializing parameters for early stop
global total_iterations    # Total iterations
global best_validation_accuracy    # Best validation accuracy
global last_improvement    # last iteration with improvement
best_validation_accuracy = 0.0    # Recent best validation accuracy
last_improvement = 0     # last iteration with improvement
require_improvement = 1000    # If no improvements have done within 1000 iterations, stop trainning.


for i in range(10000000):
    x_batch, y_batch_vec, y_batch_idx = next_batch(batch_size, X_impred_train, Y_train_vec, Y_train)    # Loading in the next batch of trainning set
    total_iterations = i
    if i%(2 * batch_size) == 0:
        #train_loss = avg_loss.eval(feed_dict = {x: x_batch, y_: y_batch})
        #print("step %d, training loss %g"%(i, train_loss))

        train_accuracy = accuracy.eval(feed_dict = {x: x_batch, y_: y_batch_vec, y_label_idx: y_batch_idx})
        print("step %d, training accuracy %g"%(i, train_accuracy))
        acc_validation = validation_accuracy(2 * batch_size, X_impred_valid, Y_valid_vec, Y_valid)


        if acc_validation > best_validation_accuracy:   # If recent validation accuracy is larger than the best one
            best_validation_accuracy = acc_validation   # update the best accuracy
            last_improvement = total_iterations         # update the id of iterations

            saver.save(sess=sess, save_path=save_path)  
            improved_str = '*'    # mark as improved
        else:
            improved_str = ''
        summary = sess.run(merged, feed_dict = {x: x_batch, y_: y_batch_vec, y_label_idx: y_batch_idx})


        writer.add_summary(summary, i)
        writer.flush()
    train_step.run(feed_dict={x: x_batch, y_: y_batch_vec, y_label_idx: y_batch_idx})    # Train the model

#print("test loss %g"%avg_loss.eval(feed_dict = {x: testX_impred, y_: testY_vec}))    # Test the model
print("test accuracy %g"%accuracy.eval(feed_dict = {x: testX_impred, y_: testY_vec, y_label_idx: testY}))    # Test the model


# Close session
sess.close()