from flask import Flask, request, jsonify
from json import dumps
import random
import requests
import string


from collections import defaultdict

MIN_LENGTH = 4
LOSE = "LOSE"
WIN = "WIN"

WORDLIST = "https://raw.githubusercontent.com/eneko/data-repository/master/data/words.txt"
base_words = requests.get(WORDLIST).text.split("\n")
base_words = filter(lambda w: w.isalpha() and w.islower(), base_words)
true_word_map = {w: True for w in base_words if len(w) >= MIN_LENGTH}

import math
import requests
FREQLIST = "http://norvig.com/ngrams/count_1w.txt"
freq_words = requests.get(FREQLIST).text.split("\n")
freqs = {w: math.log(int(f)) for (w, f) in [line.split("\t") for line in freq_words if line]}

word_map = {w: True for w in base_words if len(w) >= MIN_LENGTH and (
    (w in freqs and freqs[w] > 17) or
    random.random() < math.e**(freqs.get(w, 0) - 17))
}

print word_map
print("Words", len(word_map))
words_starting_with = defaultdict(lambda: set())
for w in word_map.keys():
    for prefix_len in range(len(w)):
        words_starting_with[w[:prefix_len]] |= set(w[prefix_len:prefix_len+1])
words_starting_with = dict(words_starting_with)
print "loaded", len(word_map)

def get_options(prefix):
    return [v for v in words_starting_with.get(prefix, []) if (prefix + v) not in word_map]

def decide(prefix):
    prefix = prefix.lower()
    options = get_options(prefix)
    scores = {o: decide(prefix + o) for o in options}
    winnables = [move for move in scores if scores[move][1] == LOSE]
    if winnables:
        return (winnables, WIN)
    return (options, LOSE)

def current_state():
    ret = [c['parameters'] for c in request.json['result']['contexts'] if c['name'] == 'state']
    if ret: return ret[0]
    return {}

def current_parameters():
    return request.json['result']['parameters']

def current_action():
    return request.json['result']['action']


def finish(txt, new_contexts, state):
    response = {
        "speech": txt,
        "displayText": txt,
        "data": { },
        "contextOut": new_contexts + [{
            "name":"state",
            "lifespan":30,
            "parameters": state
        }],
        "source": "GhostMaster"
    }
    print "Returning", response
    return jsonify(response)

app = Flask(__name__)
@app.route("/", methods=['POST'])
def hook():
    params = current_parameters()
    state = current_state()
    action = current_action()

    print params, state, action

    first_player = params.get('choseFirstPlayer')
    if not first_player:
        first_player = state.get('firstPlayer', 'human')

    so_far = state.get('soFar', '').upper()
    new_contexts = []

    if request.json['result']['action'] == "game.user-challenge":
        if so_far.lower() not in true_word_map:
            txt = "I haven't completed a word yet. "
            if so_far.lower() in words_starting_with:
                my_word = random.choice([w for w in word_map if w.startswith(so_far.lower())])
                txt += "And the word I'm thinking of is %s. That's %s. I win!"%(my_word, "-".join(my_word.upper()))
        else:
            txt = "Darn, you're right! %s is a word. You win!"%so_far
        return finish(txt, [{ "name":"await-letter", "lifespan":0 },{"name": "user-challenge", "lifespan": 0}], state)

    if request.json['result']['action'] == "game.rescue":
        rescue_word = params.get('rescueWord').lower()
        print "rescue", rescue_word, "sw?", so_far.lower()
        if not rescue_word.startswith(so_far.lower()):
            txt = "Yeah, but %s doesn't start with %s. I win!"%(rescue_word, "-".join(so_far))
        elif rescue_word in true_word_map:
            txt = "Darn, you're right! %s is a word. You win!"%rescue_word
        else:
            txt = "Nice try. I know a lot of words, and %s isn't one of them."%"-".join(rescue_word.upper())
        return finish(txt, [{ "name":"challenge", "lifespan":0 }], state)

    if  request.json['result']['action'] == "game.begin":
        txt = "Sure thing! "
        so_far = ""
        new_contexts += [{
            "name":"await-letter",
            "lifespan":1
        }, {
            "name": "challenge",
            "lifespan": 0
        }]
        first_player = "computer" if first_player == "human" else "human"
        if first_player == "human":
            txt += "Go right ahead!"
        else:
            decisions = string.ascii_lowercase
            print "decision firsst", decisions
            first_move = random.choice(decisions).upper()
            so_far += first_move
            txt += "I start with the letter %s"%first_move
        return finish(txt, new_contexts, {"soFar": so_far, "firstPlayer": first_player})

    if  request.json['result']['action'] == "game.supplyLetter":
        txt = random.choice(["OK", "Interesting", "Right", "Fine", "Let's see"]) + ". "
        so_far += params['userSuppliedLetter'].upper()
        decisions = decide(so_far)[0]
        print "decision mid", decisions
        if so_far in word_map:
            txt += "You've completd the word %s! I win!"%so_far
            so_far = ""
        elif not decisions:
            txt += "I challenge you! There's no word that starts with %s. Can you name one?"%"-".join(so_far)
            new_contexts += [{
                "name":"challenge",
                "lifespan":5
            }, {
                "name": "await-letter",
                "lifespan": 0
            }]
        else:
            next_move = random.choice(decisions).upper()
            so_far += next_move
            new_contexts += [{
                "name":"await-letter",
                "lifespan":1
            }]
            txt  += "I add %s. That makes %s"%(next_move, "-".join(so_far))
        state["soFar"] = so_far
        return finish(txt, new_contexts, state)
    return jsonify({"error": "Action not understood"})
