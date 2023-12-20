import numpy as np
from numba import njit, prange

DISCOUNT = 1.0
CARD_MIN = 1
CARD_MAX = 10
PLAY_MINVAL = 2
PLAY_MAXVAL = 21
DECK_PROBS = np.ones(10) / 10 # Sampled from "infinite" deck



@njit
def set_seed(value):
    """
    See: https://github.com/numba/numba/issues/6002
    """
    np.random.seed(value)
    

@njit
def draw_card():
    return np.random.multinomial(1, DECK_PROBS).argmax() + 1


@njit
def compute_reward(value_cards_player, value_cards_dealer):
    if value_cards_player == value_cards_dealer == 21:
        reward = 0 # draw
    elif value_cards_player > 21:
        reward = -1 # lose
    elif value_cards_dealer > 21:
        reward = 1 # win
    elif value_cards_player == value_cards_dealer:
        reward = 0 # draw
    elif value_cards_player > value_cards_dealer:
        reward = 1 # win
    else:
        reward = -1 # lose
    
    return reward


@njit
def init_game():
    value_cards_player = np.array([draw_card(), draw_card()])
    has_usable_ace = 1 in value_cards_player
    value_cards_player = value_cards_player.sum() + 10 * has_usable_ace
    
    dealers_card = draw_card() # Dealer's one-showing card
    
    return value_cards_player, has_usable_ace, dealers_card


@njit
def update_hand(value_cards):
    """
    Update the value of the hand for either the player
    or the dealer
    """
    new_card = draw_card()
    has_usable_ace = False
    
    if (new_card == 1) and (value_cards <= 10):
        has_usable_ace = True
        value_cards = value_cards + 11 # Make use of the ace
    else:
        value_cards = value_cards + new_card

    return value_cards, has_usable_ace


@njit
def state_to_ix(value_cards_player, has_usable_ace, dealers_card):
    ix_value_cards = value_cards_player - PLAY_MINVAL
    ix_has_usable_ace = int(has_usable_ace)
    ix_dealers_card = dealers_card - CARD_MIN
    
    ixs = ix_value_cards, ix_has_usable_ace, ix_dealers_card
    return ixs


@njit
def step_player(
    value_cards_player,
    has_usable_ace,
    dealers_card,
    policy
):
    continue_play = True
    # turn into indices
    ixs = state_to_ix(value_cards_player, has_usable_ace, dealers_card)
    ix_value_cards, ix_has_usable_ace, ix_dealers_card = ixs
    action = policy[ix_value_cards, ix_has_usable_ace, ix_dealers_card].argmax()
    
    if action == 1:
        value_cards_player, has_usable_ace_new = update_hand(value_cards_player)
        has_usable_ace = has_usable_ace or has_usable_ace_new
        
    if (value_cards_player >= 21) or (action == 0):
        continue_play = False
    
    return value_cards_player, has_usable_ace, action, continue_play


@njit
def dealer_strategy(dealers_card):
    """
    The dealer hits or sticks according to a fixed strategy:
    Stick on any sum of 17 or greater and hit otherwise
    """
    value_cards_dealer = dealers_card + 10 * (dealers_card == 1)
    while value_cards_dealer < 17:
        value_cards_dealer, _ = update_hand(value_cards_dealer)
        
    return value_cards_dealer

    
@njit
def play_single(value_cards_player, has_usable_ace, dealers_card, policy):
    reward = 0
    
    continue_play = True
    while continue_play:
        value_cards_player, has_usable_ace, action, continue_play = step_player(
            value_cards_player, has_usable_ace, dealers_card, policy
        )
    
    value_cards_dealer = dealer_strategy(dealers_card)
    
    reward = compute_reward(value_cards_player, value_cards_dealer)
    return reward, (value_cards_player, value_cards_dealer)


@njit
def play_single_hist(value_cards_player, has_usable_ace, dealers_card, policy):
    """
    Play game and store intermediate steps
    """
    reward = 0
    
    states = [[value_cards_player, has_usable_ace, dealers_card]]
    rewards = []
    actions = []
    
    continue_play = True
    while continue_play:
        value_cards_player, has_usable_ace, action, continue_play = step_player(
            value_cards_player, has_usable_ace, dealers_card, policy
        )
        
        rewards.append(0)
        actions.append(action)
        states.append([value_cards_player, has_usable_ace, dealers_card])
    
    value_cards_dealer = dealer_strategy(dealers_card)
    
    reward = compute_reward(value_cards_player, value_cards_dealer)
    rewards.append(reward)
    actions.append(0) # final dummy action
    
    hist = (
        states,
        actions,
        rewards
    )
    
    return reward, (value_cards_player, value_cards_dealer), hist


@njit
def single_first_visit_mc(policy):    
    player_value_cards, ace, dealer_card = init_game()
        
    reward, values, hist = play_single_hist(player_value_cards, ace, dealer_card, policy=policy)
    hist_state, _, hist_reward = hist
    T = len(hist_state)

    elements = []
    sim_reward = 0
    for t in range(-1, -(T + 1), -1):
        sim_reward = DISCOUNT * sim_reward + hist_reward[t]
        current_state = hist_state[t]
        previous_states = hist_state[:t]
        value_cards_player, has_usable_ace, dealers_card = current_state
        
        first_visit = current_state not in previous_states
        if first_visit:
            ixs = state_to_ix(value_cards_player, has_usable_ace, dealers_card)
                        
            element = (ixs, sim_reward)
            elements.append(element)
        
    return elements