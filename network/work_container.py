import gym
import os

class WorkContainerBase(object):
   def __init__(self, state_space_size, action_space_size):
      self.state_size = state_space_size
      self.action_size = action_space_size

   def get_state_size(self):
      self.state_size

   def get_action_size(self):
      self.action_size

   def save_params(self, filename):
      raise ValueError("Need to implement save_params")

   def load_params(self, filename):
      raise ValueError("Need to implement load_params")

   def train_batch(
      self,
      states,
      actions,
      discounted_rewards,
      rewards,
      next_states
   ):
      raise ValueError("Need to implement train_batch")

   def predict(self, state):
      raise ValueError("Need to implement predict")
