import numpy as np
import os
import tensorflow as tf

class PendulumNetworks(object):
   def __init__(self, session, input_size, output_size, gamma=0.99, ppo_epsilon=0.2):
      self.session = session
      self.input_size = input_size
      self.output_size = output_size
      self.gamma = gamma
      self.ppo_epsilon = ppo_epsilon
      
      self.observations_ph = tf.placeholder(dtype=tf.float32, shape=[None, self.input_size], name="observations")
      # esdr = expected sum of discounted rewards
      self.esdr_ph = tf.placeholder(dtype=tf.float32, shape=[None, 1], name="expected_sum_of_discounted_rewards")
      self.v_s_ph  = tf.placeholder(dtype=tf.float32, shape=[None, 1], name="value_of_current_state") # V(s)
      self.v_sp_ph = tf.placeholder(dtype=tf.float32, shape=[None, 1], name="value_of_next_state") # V(s')
      self.r_ph    = tf.placeholder(dtype=tf.float32, shape=[None, 1], name="reward_at_time_plus_1") # r_t+1; r'
      self.actions_ph = tf.placeholder(dtype=tf.float32, shape=[None, self.output_size], name="actions")

      advantage = self.r_ph + self.gamma*self.v_sp_ph - self.v_s_ph

      policy_means, policy_stdevs = self.build_actor("policy_new")
      policy_means_prev, policy_stdevs_prev = self.build_actor("policy_old", trainable=False)

      value = self.build_critic("value")

      actor_ratio_numerator_log = -tf.log(policy_stdevs) + -0.5*tf.square(
            (policy_means - self.actions_ph)/policy_stdevs
      )
      actor_ratio_denominator_log = -tf.log(policy_stdevs_prev) + -0.5*tf.square(
            (policy_means_prev - self.actions_ph)/policy_stdevs_prev
      )
      
      actor_ratio = tf.exp(actor_ratio_numerator_log - actor_ratio_denominator_log)
      
      self.actor_loss = -1.0*tf.reduce_mean(
         tf.minimum(
            actor_ratio*advantage,
            advantage*tf.clip_by_value(actor_ratio, 1 - self.ppo_epsilon, 1 + self.ppo_epsilon)
         )
      )
      self.actor_optimizer = tf.train.AdamOptimizer(learning_rate=1e-4).minimize(self.actor_loss)

      self.critic_loss = tf.reduce_mean(
         tf.square(value - self.r_ph - self.gamma*self.v_sp_ph)
      )
      self.critic_optimizer = tf.train.AdamOptimizer(learning_rate=5e-4).minimize(self.critic_loss)
      
      self.action_prediction_means = policy_means
      self.action_prediction_stdevs = policy_stdevs
      self.esdr_predictions = value
      
      old_params = [v for v in tf.global_variables() if "policy_old" in v.name]
      new_params = [v for v in tf.global_variables() if "policy_new" in v.name]

      self.assignments = [op.assign(np) for op, np in zip(old_params, new_params)]

      self.session.run(tf.global_variables_initializer())
      self.saver = tf.train.Saver()

   def update_prev_actor(self):
      '''
      Assign the new params to the old params of the policy network.
      '''
      self.session.run(self.assignments)

   def build_actor(self, scope_name, reuse_scope=False, trainable=True):
      with tf.variable_scope(scope_name, reuse=reuse_scope):
         W1p = tf.get_variable(
            "w1p",
            [self.input_size, 128],
            #initializer=tf.initializers.random_normal(stddev=0.01),
            initializer=tf.initializers.orthogonal,
            trainable=trainable
         )
         b1p = tf.get_variable(
            "b1p",
            [128],
            initializer=tf.initializers.random_normal(stddev=0.01),
            trainable=trainable
         )
         W2p_means = tf.get_variable(
            "w2pmeans",
            [128, self.output_size],
            #initializer=tf.initializers.random_normal(stddev=0.01),
            initializer=tf.initializers.orthogonal,
            trainable=trainable                
         )
         W2p_stdevs = tf.get_variable(
            "w2pstdevs",
            [128, self.output_size],
            #initializer=tf.initializers.random_normal(stddev=0.01),
            initializer=tf.initializers.orthogonal,
            trainable=trainable
         )
         b2p_means = tf.get_variable(
            "b2pmeans",
            [self.output_size],
            initializer=tf.initializers.random_normal(stddev=0.01),
            trainable=trainable
         )
         b2p_stdevs = tf.get_variable(
            "b2pstdevs",
            [self.output_size],
            initializer=tf.initializers.random_normal(stddev=0.01),
            trainable=trainable
         )

         l1p = tf.nn.relu(tf.matmul(self.observations_ph, W1p) + b1p)
         # this will need to be changed to accommodate the range and character of action values
         l2p_means = tf.matmul(l1p, W2p_means) + b2p_means
         # Trying to start with a large standard deviation to encourage exploration early on.
         l2p_stdevs = tf.matmul(l1p, W2p_stdevs) + b2p_stdevs
         policy_means = 2*tf.nn.tanh(l2p_means)

         policy_stdevs = tf.maximum(tf.nn.softplus(l2p_stdevs), 1e-5)

         return policy_means, policy_stdevs

   def build_critic(self, scope_name, reuse_scope=False, trainable=True):
      with tf.variable_scope(scope_name, reuse=reuse_scope):
         W1v = tf.get_variable(
            "w1v",
            [self.input_size, 128],
            initializer=tf.initializers.orthogonal,
            trainable=trainable
         )
         b1v = tf.get_variable(
            "b1v",
            [128],
            initializer=tf.initializers.random_normal(stddev=0.01),
            trainable=trainable
         )
         l1v = tf.nn.relu(tf.matmul(self.observations_ph, W1v) + b1v)

         W2v = tf.get_variable(
            "w2v",
            [128, 1],
            initializer=tf.initializers.orthogonal,
            trainable=trainable
         )
         b2v = tf.get_variable(
            "b2v",
            [1],
            initializer=tf.initializers.random_normal(stddev=0.01),
            trainable=trainable
         )
         l2v = tf.matmul(l1v, W2v) + b2v

         return l2v

   # For advantage:
   #    Add single timestep reward samples
   #    Add placeholders for estimated V(s) and V(s')
   def train_batch(
      self,
      states,
      actions,
      discounted_rewards,
      rewards=None,
      next_states=None
   ):
      '''
      Expects inputs to be numpy arrays of shape:
         states = [batch_size, num_state_features]
         actions = [batch_size, num_available_actions]
         discounted_rewards = [batch_size, 1]
         next_states = [batch_size, num_state_features]
      
      The idea is that all episodes have been parsed through and shuffled into
      one big batch of training data.
      '''
      print("states", states.shape)
      print("actions", actions.shape)
      print("discounted_rewards", discounted_rewards.shape)
      print("rewards", rewards.shape)
      print("next states", next_states.shape)

      advantage_feeds = {
         self.observations_ph: states
      }

      advantage_fetches = self.esdr_predictions

      v_predictions = self.session.run(advantage_fetches, feed_dict=advantage_feeds)

      esdr_estimate_feeds = {
         self.observations_ph: next_states
      }

      v_sp_predictions = self.session.run(advantage_fetches, feed_dict=esdr_estimate_feeds)

      optimize_feeds = {
         self.observations_ph: states,
         self.esdr_ph: discounted_rewards,
         self.v_s_ph: v_predictions,
         self.actions_ph: actions,
         self.v_sp_ph: v_sp_predictions,
         self.r_ph: rewards
      }

      optimize_fetches = [
         self.actor_loss,
         self.action_prediction_means,
         self.action_prediction_stdevs,
         self.esdr_predictions,
         self.actor_optimizer,
         self.critic_optimizer
      ]

      loss, action_prediction_means, action_prediction_stdevs, esdr_predictions, _1, _2 = self.session.run(optimize_fetches, feed_dict=optimize_feeds)

      return loss, action_prediction_means, action_prediction_stdevs, esdr_predictions

   def predict(self, state):
      '''
      Expects state to have the shape [num_state_features]
      '''

      feeds = {
         self.observations_ph: np.array([state])
      }

      print("shape of observation being fed in:", np.array([state]).shape, state.shape)

      fetches = [
         self.action_prediction_means,
         self.action_prediction_stdevs,
         self.esdr_predictions
      ]
      action_prediction_means, action_prediction_stdevs, esdr_predictions = self.session.run(fetches, feed_dict=feeds)
      ep_action_t = np.random.normal(
         loc=action_prediction_means[0],
         scale=action_prediction_stdevs[0]
      )
      ep_action_t = min(max(ep_action_t, [-2.0]), [2.0])
      return ep_action_t, action_prediction_means, action_prediction_stdevs, esdr_predictions

   def save_params(self, filename):
      self.saver.save(self.session, filename)

   def load_params(self, filename):
      self.saver.restore(self.session, filename)
