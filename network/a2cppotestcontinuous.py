
# coding: utf-8

# In[1]:


import datetime
import gym
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import tensorflow as tf


# In[2]:


class FfAgentContinuous(object):
    def __init__(self, session, input_size, output_size, gamma=0.99, ppo_epsilon=0.2):
        self.session = session
        self.input_size = input_size
        self.output_size = output_size
        self.gamma = gamma
        self.ppo_epsilon = ppo_epsilon
        
        self.observations_ph = tf.placeholder(dtype=tf.float32, shape=[None, self.input_size])
        # esdr = expected sum of discounted rewards
        self.esdr_ph = tf.placeholder(dtype=tf.float32, shape=[None, 1])
        self.v_s_ph  = tf.placeholder(dtype=tf.float32, shape=[None, 1]) # V(s)
        self.v_sp_ph = tf.placeholder(dtype=tf.float32, shape=[None, 1]) # V(s')
        self.r_ph    = tf.placeholder(dtype=tf.float32, shape=[None, 1]) # r_t+1; r'
        self.actions_ph = tf.placeholder(dtype=tf.float32, shape=[None, self.output_size])

        advantage = self.r_ph + self.gamma*self.v_sp_ph - self.v_s_ph

        policy_means, policy_stdevs = self.buildActor("policy_new")
        policy_means_prev, policy_stdevs_prev = self.buildActor("policy_old", trainable=False)

        value = self.buildCritic("value")

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
        
    def updatePrevActor(self):
        '''
        Assign the new params to the old params of the policy network.
        '''
        self.session.run(self.assignments)
        
    def buildActor(self, scope_name, reuse_scope=False, trainable=True):
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

    def buildCritic(self, scope_name, reuse_scope=False, trainable=True):
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
    def trainSarBatches(self, states, actions, discounted_rewards, rewards=None, next_states=None):
        '''
        Expects inputs to be numpy arrays of shape:
            states = [batch_size, num_state_features]
            actions = [batch_size, num_available_actions]
            discounted_rewards = [batch_size, 1]
            next_states = [batch_size, num_state_features]
        
        The idea is that all episodes have been parsed through and shuffled into
        one big batch of training data.
        '''
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
        
        loss, action_prediction_means, action_prediction_stdevs, esdr_predictions, _1, _2 =             self.session.run(optimize_fetches, feed_dict=optimize_feeds)
        
        return loss, action_prediction_means, action_prediction_stdevs, esdr_predictions
    
    def predict(self, state):
        '''
        Expects state to have the shape [num_state_features]
        '''
        
        feeds = {
            self.observations_ph: np.array([state])
        }
        #print("state received by agent:", state)
        fetches = [
            self.action_prediction_means,
            self.action_prediction_stdevs,
            self.esdr_predictions
        ]
        action_prediction_means, action_prediction_stdevs, esdr_predictions = self.session.run(fetches, feed_dict=feeds)
        return action_prediction_means, action_prediction_stdevs, esdr_predictions


# In[3]:


def prepSarData(states, actions, rewards, gamma=0.99):
    '''
    Converts temporally synced lists of states, actions, and rewards into shuffled
    numpy matrices for training.
    '''
    #print("lengths of states, actions, rewards:", len(states), len(actions), len(rewards))
    
    #print("shape of sample current state:", len(states[0]))
    
    next_states = states[1:]
    states = states[:-1]
    actions = actions[:-1]
    rewards = rewards[:-1]
    discounted_sum_rewards = 0
    discounted_rewards = []
    for i in range(len(rewards) - 1, -1, -1):
        discounted_sum_rewards = gamma*discounted_sum_rewards + rewards[i]
        discounted_rewards.append(discounted_sum_rewards)
    discounted_rewards = np.expand_dims(np.array(discounted_rewards[::-1]), axis=1)
    
    #print("shape of sample current state:", len(states[0]))
    #print("shape of sample next state:", len(next_states[0]))
    
    actions = np.array(actions)
    states = np.array(states)
    rewards = np.expand_dims(np.array(rewards), axis=1)
    next_states = np.array(next_states)
    
    indices = [i for i in range(len(actions))]
    np.random.shuffle(indices)
    
    #print("shape of next states:", next_states.shape)
    
    actions_shuffled = actions[indices]
    states_shuffled = states[indices]
    discounted_rewards_shuffled = discounted_rewards[indices]
    rewards_shuffled = rewards[indices]
    next_states_shuffled = next_states[indices]
    
    return states_shuffled, actions_shuffled, discounted_rewards_shuffled, rewards_shuffled, next_states_shuffled


# In[5]:


def accumulateData(env, agent, max_steps=1000, max_rollouts=40):
    states = []
    actions = []
    rewards = []
    for rollout_count in range(max_rollouts):
        ep_states = []
        ep_actions = []
        ep_rewards = []
        ep_state_t = env.reset()
        ep_states.append(ep_state_t)
        for t in range(max_steps):
            ret_vals = agent.predict(ep_state_t)
            ep_action_t = np.random.normal(loc=ret_vals[0][0], scale=ret_vals[1][0])
            #print(ep_action_t)
            ep_action_t = min(max(ep_action_t, [-2.0]), [2.0])
            #print(ep_action_t)
            ep_state_tp1, ep_reward_tp1, done, _ = env.step(ep_action_t)

            ep_actions.append(ep_action_t)
            ep_states.append(ep_state_tp1)
            ep_rewards.append(ep_reward_tp1)
            if done:
                ep_states.pop(-1)
                #ep_rewards.pop(-1)
                break
            ep_state_t = ep_state_tp1
        states.append(ep_states)
        actions.append(ep_actions)
        rewards.append(ep_rewards)
        #print("length of sample state:", len(states[0][0]))
    return states, actions, rewards


# In[6]:


def renderAgent(env, agent, debug=False):
    state_t = env.reset()
    rewards = 0
    actions = []
    means = []
    stdevs = []
    iterator_variable = 0
    while iterator_variable < 1000:
        ret_vals = agent.predict(state_t)
        action_t = np.random.normal(loc=ret_vals[0][0], scale=ret_vals[1][0])
        #print(ep_action_t)
        action_t = min(max(action_t, [-2.0]), [2.0])
        actions.append(action_t)
        means.append(ret_vals[0][0])
        stdevs.append(ret_vals[1][0])
        #print(ep_action_t)
        state_tp1, reward_tp1, done, _ = env.step(action_t)
        rewards += reward_tp1
        env.render()
        state_t = state_tp1
        if done:
            print("Rewards from rendering:", rewards)
            break
    return actions, stdevs, means


# #print(type(gym.envs.registry.all()))
# env_ids = [espec.id for espec in gym.envs.registry.all()]
# for e in sorted(env_ids):
#     print(e)
# 

# In[7]:


pendulum = gym.make("Pendulum-v0")
session = tf.Session()
print(pendulum.observation_space.shape)
print(pendulum.action_space)
num_actions = len(pendulum.action_space.high)
agent = FfAgentContinuous(session, pendulum.observation_space.shape[0], num_actions)

session.run(tf.global_variables_initializer())
saver = tf.train.Saver()


# In[8]:


# Optionally load a checkpoint and continue training.
#saver.restore(session, "./checkpoints/periodic_-1159.562864019951_2020-01-05-04-22-44.191582")


# In[23]:


average_rewards = []
average_stdevs = []
last_saved_at = 0
for i in range(300):
    states, actions, rewards = accumulateData(pendulum, agent)
    #print(actions[0:10])
    #print(rewards[0:10])
    states_pro = []
    actions_pro = []
    rewards_pro = []
    discounted_rewards_pro = []
    next_states_pro = []
    last_10_average_rewards = np.average(average_rewards[-10:])
    if (len(average_rewards) > 20) and (last_10_average_rewards >= -900) and (i - last_saved_at > 50) or ((i > 0) and average_rewards[-1] >= -400):
        print("Saving the model after finding last 10 average rewards of:", last_10_average_rewards)
        save_name = "holyfuckingshit_" + str(last_10_average_rewards) + "_" + str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")
        save_dir = os.path.join("checkpoints", save_name)
        saver.save(session, save_dir)
        last_saved_at = i
    elif i % 1000 == 0 and i > 0:
        save_name = "periodic_" + str(last_10_average_rewards) + "_" + str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")
        save_dir = os.path.join("checkpoints", save_name)
        saver.save(session, save_dir)
    if i % 20 == 0 and i > 0:
        plt.figure()
        plt.plot(average_stdevs)
        plt.title("Average stdevs so far")
        plt.figure()
        plt.plot(average_rewards)
        plt.title("average rewards so far")

        plottable_actions, plottable_stdevs, plottable_means = renderAgent(pendulum, agent)
        plt.figure()
        max_stddev = np.max(plottable_stdevs)
        plt.errorbar(range(len(plottable_means)), plottable_means, plottable_stdevs/max_stddev, linestyle='None')
        plt.scatter(range(len(plottable_actions)), plottable_actions, color='y')
        plt.scatter(range(len(plottable_means)), plottable_means, color='r')
        plt.title("Actions Taken in Rendered Environment")
        plt.xlabel("max stddev:" + str(max_stddev))
        plt.show()
        plt.close('all')

    for j in range(len(actions)):
        ret = prepSarData(states[j], actions[j], rewards[j])
        states_pro.append(ret[0])
        actions_pro.append(ret[1])
        discounted_rewards_pro.append(ret[2])
        rewards_pro.append(ret[3])
        next_states_pro.append(ret[4])
        
        mean_reward = np.average(ret[1])
        stdev_reward = np.std(ret[1])

    for k in range(5*len(states_pro)):
        train_index = np.random.choice(a=range(len(states_pro)))
        #print("Shape of selected next states:", next_states_pro[train_index].shape)
        #print("Shape of selected states:", states_pro[train_index].shape)
        ret = agent.trainSarBatches(
            states_pro[train_index],
            actions_pro[train_index],
            discounted_rewards_pro[train_index],
            rewards_pro[train_index],
            next_states_pro[train_index]
        )
        if np.isnan(ret[0]):
            print("Received nan loss, stopping training.")
            pendulum.close()
            sys.exit(-1)
    agent.updatePrevActor()
    print(i)
    average_reward = np.average([sum(r) for r in rewards])
    print("average reward: ", average_reward, "stdevs:", np.average(np.squeeze(ret[2])), "losses:", np.average(np.squeeze(ret[0])))
    average_stdevs.append(np.average(np.squeeze(ret[2])))
    average_rewards.append(average_reward)

plt.figure()
plt.plot(average_rewards)
plt.show()
#pendulum.close()


# In[24]:


def renderAndPlot():
    plottable_actions, plottable_stdevs, plottable_means = renderAgent(pendulum, agent)
    plt.figure()
    max_stddev = np.max(plottable_stdevs)
    plt.errorbar(range(len(plottable_means)), plottable_means, plottable_stdevs/max_stddev, linestyle='None')
    plt.scatter(range(len(plottable_actions)), plottable_actions, color='y')
    plt.scatter(range(len(plottable_means)), plottable_means, color='r')
    plt.title("Actions Taken in Rendered Environment")
    plt.xlabel("max stddev:" + str(max_stddev))
    plt.show()
    plt.close('all')


# In[25]:


renderAndPlot()


# In[ ]:


for i in range(100):
    renderAndPlot()

