import datetime
import gym
import matplotlib.pyplot as plt
import numpy as np
import os
import tensorflow as tf

#from network.pendulum_networks import PendulumNetworks
from pendulum_networks import PendulumNetworks

class WorkContainer(object):
   def __init__(self, networks, environment, reward_gamma=0.99):
      # Policy and value networks (ugliness)
      self.networks = networks
      self.env = environment
      self.state_size  = len(self.env.observation_space.high)
      self.action_size = len(self.env.action_space.high)
      self.gamma = reward_gamma

   def get_state_size(self):
      return self.state_size

   def get_action_size(self):
      return self.action_size

   def save_params(self, filename):
      self.networks.save_params(filename)

   def load_params(self, filename):
      self.networks.load_params(filename)

   def train_batch(
      self,
      states,
      actions,
      discounted_rewards,
      rewards,
      next_states
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

      ret_vals = self.networks.train_batch(
         states,
         actions,
         discounted_rewards,
         rewards,
         next_states
      )
      return ret_vals

   def perform_rollout(self, max_steps=1000):
      '''
      Performs a single rollout episode with the current environment and
      policy. Returns the actions, states, and rewards obtained during the
      rollout. This is un-processed temporal data, so all rewards are sampled
      from a single timestep.
      '''
      ep_actions = []
      ep_states = []
      ep_rewards = []
      ep_state_t = self.env.reset()
      ep_states.append(ep_state_t)
      for t in range(max_steps):
         #print("shape of ep_state_t", ep_state_t.shape)
         ret_vals = self.networks.predict(ep_state_t)
         ep_action_t = ret_vals[0]
         #print(ep_action_t)
         ep_state_tp1, ep_reward_tp1, done, _ = self.env.step(ep_action_t)

         ep_actions.append(ep_action_t)
         ep_states.append(ep_state_tp1)
         ep_rewards.append(ep_reward_tp1)
         if done:
            ep_states.pop(-1)
            break
         ep_state_t = ep_state_tp1

      #return ep_states, ep_actions, ep_rewards
      return self.prep_sar_data(ep_states, ep_actions, ep_rewards)

   def prep_sar_data(self, states, actions, rewards):
      '''
      Takes temporally sequenced data with single timestep reward samples and
      converts rewards into samples of sum of discounted rewards using the
      single rollout. Basically a conversion from an episode's worth of SAR data
      to an episode's worth of SARSA data.
      '''
      next_states = states[1:]
      states = states[:-1]
      actions = actions[:-1]
      rewards = rewards[:-1]
      discounted_rewards = []
      discounted_sum_rewards = 0.0

      for i in range(len(rewards) - 1, -1, -1):
         discounted_sum_rewards = self.gamma*discounted_sum_rewards + rewards[i]
         discounted_rewards.append(discounted_sum_rewards)

      discounted_rewards = np.expand_dims(
         np.array(discounted_rewards[::-1]),
         axis=1
      )

      actions = np.array(actions)
      states = np.array(states)
      rewards = np.expand_dims(np.array(rewards), axis=1)
      next_states = np.array(next_states)

      ret_dict = {
         "states": states,
         "actions": actions,
         "discounted_rewards": discounted_rewards,
         "rewards": rewards,
         "next_states": next_states
      }
      print("states shape from rollout:", states.shape)
      print("actions shape from rollout:", actions.shape)
      print("discounted_rewards shape from rollout:", discounted_rewards.shape)
      print("rewards shape from rollout:", rewards.shape)
      print("next_states shape from rollout:", next_states.shape)

      #return states, actions, discounted_rewards, rewards, next_states
      return ret_dict

def render_agent(env, agent, debug=False):
    state_t = env.reset()
    rewards = 0
    actions = []
    means = []
    stdevs = []
    iterator_variable = 0
    while iterator_variable < 1000:
        ret_vals = agent.predict(state_t)
        action_t = np.random.normal(loc=ret_vals[1][0], scale=ret_vals[2][0])
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

def accumulate_data(wc, max_rollouts=40):
   rollout_returns = []
   for rollout_count in range(max_rollouts):
      # Episode states, episode actions, episode rewards
      #ep_states, ep_actions, ep_rewards = wc.perform_rollout()
      episode_metadata = wc.perform_rollout()
      # states.append(ep_states)
      # actions.append(ep_actions)
      # rewards.append(ep_rewards)
      rollout_returns.append(episode_metadata)

   return rollout_returns

if __name__ == "__main__":
   pendulum = gym.make("Pendulum-v0")
   session = tf.Session()
   print(pendulum.observation_space.shape)
   print(pendulum.action_space)
   num_actions = len(pendulum.action_space.high)
   agent = PendulumNetworks(
      session,
      pendulum.observation_space.shape[0],
      num_actions
   )

   wc = WorkContainer(agent, pendulum)

   average_rewards = []
   average_stdevs = []
   last_saved_at = 0
   for i in range(600):
      # Collect data
      rollout_returns = accumulate_data(wc)
      last_10_average_rewards = np.average(average_rewards[-10:])

      # Save criteria
      if (len(average_rewards) > 20) and (last_10_average_rewards >= -900) and (i - last_saved_at > 50) or ((i > 0) and average_rewards[-1] >= -400):
         print("Saving the model after finding last 10 average rewards of:", last_10_average_rewards)
         save_name = "holyfuckingshit_" + str(last_10_average_rewards) + "_" + str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")
         save_dir = os.path.join("checkpoints", save_name)
         wc.save_params(save_dir)
         last_saved_at = i
      elif i % 1000 == 0 and i > 0:
         save_name = "periodic_" + str(last_10_average_rewards) + "_" + str(datetime.datetime.today()).replace(":", "-").replace(" ", "-")
         save_dir = os.path.join("checkpoints", save_name)
         wc.save_params(save_dir)

      # Render/plot criteria
      # if i % 500 == 0 and i > 0:
      #    plt.figure()
      #    plt.plot(average_stdevs)
      #    plt.title("Average stdevs so far")
      #    plt.figure()
      #    plt.plot(average_rewards)
      #    plt.title("average rewards so far")

      #    plottable_actions, plottable_stdevs, plottable_means = render_agent(wc.env, wc.networks)
      #    plt.figure()
      #    max_stddev = np.max(plottable_stdevs)
      #    plt.errorbar(range(len(plottable_means)), plottable_means, plottable_stdevs/max_stddev, linestyle='None')
      #    plt.scatter(range(len(plottable_actions)), plottable_actions, color='y')
      #    plt.scatter(range(len(plottable_means)), plottable_means, color='r')
      #    plt.title("Actions Taken in Rendered Environment")
      #    plt.xlabel("max stddev:" + str(max_stddev))
      #    plt.show()
      #    plt.close('all')
      if i % 20 == 0 and i > 0:
         render_agent(wc.env, wc.networks)

      # Train on collected data
      states_pro = []
      actions_pro = []
      rewards_pro = []
      discounted_rewards_pro = []
      next_states_pro = []
      ret = None
      for j in range(len(rollout_returns)):
         states_pro.append(rollout_returns[j]["states"])
         actions_pro.append(rollout_returns[j]["actions"])
         discounted_rewards_pro.append(rollout_returns[j]["discounted_rewards"])
         rewards_pro.append(rollout_returns[j]["rewards"])
         next_states_pro.append(rollout_returns[j]["next_states"])

      for k in range(5*len(states_pro)):
         train_index = np.random.choice(a=range(len(states_pro)))
         ret = wc.train_batch(
            states_pro[train_index],
            actions_pro[train_index],
            discounted_rewards_pro[train_index],
            rewards_pro[train_index],
            next_states_pro[train_index]
         )
         if np.isnan(ret[0]):
            print("Received nan loss, stopping training.")
            sys.exit(-1)
      wc.networks.update_prev_actor()
      print(i)
      average_reward = np.average([sum(r["rewards"]) for r in rollout_returns])
      print("average reward: ", average_reward, "stdevs:", np.average(np.squeeze(ret[2])), "losses:", np.average(np.squeeze(ret[0])))
      average_stdevs.append(np.average(np.squeeze(ret[2])))
      average_rewards.append(average_reward)

   plt.figure()
   plt.plot(average_rewards)
   plt.show()
