import gym
import os

class WorkContainerBase(object):
   def __init__(self, networks, env_name=None):
      # Policy and value networks (ugliness)
      self.networks = networks
      self.env_name = env_name
      self.env = gym.make(self.env_name)
      self.state_size  = len(self.env.observation_space.high)
      self.action_size = len(self.env.action_space.high)

   def get_state_size(self):
      self.state_size

   def get_action_size(self):
      self.action_size

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
      for t in range(max_steps):
         ret_vals = agent.predict(ep_state_t)
         ep_action_t = ret_vals[0]
         ep_state_tp1, ep_reward_tp1, done, _ = env.step(ep_action_t)

         ep_actions.append(ep_action_t)
         ep_states.append(ep_state_tp1)
         ep_rewards.append(ep_reward_tp1)
         if done:
            ep_states.pop(-1)
            break
         ep_state_t = ep_state_tp1

      return ep_actions, ep_states, ep_rewards



def prep_sar_data(states, actions, rewards, gamma=0.99):
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

   for i in range(len(rewards) - 1, -1, -1):
      discounted_sum_rewards = gamma*discounted_sum_rewards + rewards[i]
      discounted_rewards.append(discounted_sum_rewards)

   discounted_rewards = np.expand_dims(
      np.array(discounted_rewards[::-1]),
      axis=1
   )

   actions = np.array(actions)
   states = np.array(states)
   rewards = np.expand_dims(np.array(rewards), axis=1)
   next_states = np.array(next_states)

   return actions, states, discounted_rewards, rewards, next_states
