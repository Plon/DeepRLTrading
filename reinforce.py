#Pay attention to possible exploding gradient for certain hyperparameters
#torch.nn.utils.clip_grad_norm_(net.parameters(), 1) 
#Maybe implement a safety mechanism that clips gradients 
import numpy as np
import torch
torch.manual_seed(0)
import torch.optim as optim
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def optimize(optimizer: optim.Adam, loss: torch.Tensor) -> None: 
    """ Set gradients to zero, backpropagate loss, and take optimization step """
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()


def get_policy_loss(rewards: list, log_probs: list) -> torch.Tensor:
    """ Return policy loss """
    r = torch.FloatTensor(rewards).to(device)
    r = (r - r.mean()) / (r.std() + float(np.finfo(np.float32).eps))
    log_probs = torch.stack(log_probs).squeeze().to(device)
    policy_loss = torch.mul(log_probs, r).mul(-1).sum().to(device)
    return policy_loss


def reinforce(policy_network: torch.nn.Module, env, act, alpha=1e-3, weight_decay=1e-5, exploration_rate=1, exploration_decay=(1-1e-4), exploration_min=0, num_episodes=1000, max_episode_length=np.iinfo(np.int32).max, train=True, print_res=True, print_freq=100, recurrent=False, early_stopping=False, early_stopping_freq=100, val_env=None):# -> tuple[np.ndarray, np.ndarray]: 
    """
    REINFORCE/Monte Carlo policy gradient algorithm

    Args: 
        policy_network (nn.Module): the policy network. 
        env: the reinforcement learning environment that takes the action from the network and performs 
             a step where it returns the new state and the reward in addition to a flag that signals if 
             the environment has reached a terminal state.
        act: a function that uses the policy network to generate some output based on the state, and 
             then transforms that output to a problem-dependent action.
        alpha (float): the learning rate on the interval [0,1] for the policy network. 
        weight_decay (float): regularization parameter for the policy network.
        exploration_rate (number): the intial exploration rate.
        exploration_decay (number): the rate of which the exploration rate decays over time.
        exploration_min (number): the minimum exploration rate. 
        num_episodes (int): the number of episodes to be performed. Not necessarily completed episodes 
                            depending on the next parameter max_episode_length.
        max_episodes_length (int): the maximal length of a single episode. 
        train (bool): wheteher the policy network is in train or evaluation mode. 
        print_res (bool): whether to print results after some number of episodes. 
        print_freq (int): the frequency of which the results after an episode are printed. 
        recurrent (bool): whether the policy network is recurrent or not. 
        early_stopping (bool): whether or not to use early stopping.
        early_stopping_freq (int): the frequency at which to test the validation set.
        val_env: the validation environment. 
    Returns:
        reward_history (np.ndarray): the sum of rewards for all completed episodes.
        action_history (np.ndarray): the array of all actions of all completed episodes.
    """
    optimizer = optim.Adam(policy_network.parameters(), lr=alpha, weight_decay=weight_decay)
    reward_history = []
    action_history = []
    total_rewards = []
    total_actions = []
    validation_rewards = []
    completed_episodes_counter = 0
    done = False
    state = env.reset() #S_0

    if not train:
        exploration_min = 0
        exploration_rate = exploration_min
        policy_network.eval()
    else:
        policy_network.train()

    done = False
    state = env.reset() #S_0
    total_rewards = []
    total_actions = []
    completed_episodes_counter = 0
    validation_rewards = []

    for n in range(num_episodes):
        rewards = [] 
        actions = [] 
        log_probs = []  
        hx = None

        for _ in range(max_episode_length):
            action, log_prob, hx = act(policy_network, state, hx, recurrent, exploration_rate) #A_{t-1}
            state, reward, done, _ = env.step(action) # S_t, R_t 

            if done:
                break

            actions.append(action)
            rewards.append(reward) 
            log_probs.append(log_prob)
            exploration_rate = max(exploration_rate*exploration_decay, exploration_min)

        if train:
            policy_loss = get_policy_loss(rewards, log_probs)
            optimize(optimizer, policy_loss)

        total_rewards.extend(rewards)
        total_actions.extend(actions)

        if done: 
            reward_history.append(sum(total_rewards))
            action_history.append(np.array(total_actions))
            state = env.reset() #S_0
            total_rewards = []
            total_actions = []
            completed_episodes_counter += 1

        if done and print_res and (completed_episodes_counter-1) % print_freq == 0:
            print("Completed episodes: ", completed_episodes_counter)                  
            print("Actions: ", action_history[-1])
            print("Sum rewards: ", reward_history[-1])
            print("-"*20)
            print()
        
        if done and early_stopping and completed_episodes_counter % early_stopping_freq == 0:
            val_reward, _ = reinforce(policy_network, val_env, act, train=False, num_episodes=1, print_res=False, recurrent=recurrent, exploration_rate=0, exploration_min=0)
            if len(validation_rewards) > 0 and val_reward[0] < validation_rewards[-1]:
                return np.array(reward_history), np.array(action_history)
            validation_rewards.append(val_reward)

    return np.array(reward_history), np.array(action_history)
