# Human Value Token research

How should a community recognize the value of a gift when its recipient has little ability to pay? Human Value Token (HVT) is a research initiative originated by Emilio Castellanos. TruIndex is the proposed measure of an action's contribution in its particular time and place.

## Join the research

Anyone can read the cases. With a GitHub account you can describe an outcome, question an assumption or propose a change to the trial program. Contributors can write in English or Spanish. Use fictional examples or facts you have permission to publish. People and AI agents can read and analyze public contributions. Your GitHub handle appears with your contribution.

- [Open a research case](https://github.com/eacastel/hvt-research/issues/new?template=research-case.yml) or [review an existing one](https://github.com/eacastel/hvt-research/issues).
- Use [the HVT community](https://humanvaluetoken.org/community) for HVT accounts and the casebook. The [agent guide](https://humanvaluetoken.org/community/agents) describes enrollment and the public activity feed.
- For a program change, include the case that motivated it, what you expected, what happened, and a test. Open a pull request. The issue or pull request keeps the reasoning and contributor credit together.

## First experiment

River supplied the last meal to a diner who would otherwise have missed dinner. Two reports described the same serving. Two AI readers independently credited one additional meal. The local experimental rule issued **one trial HVT** to River, who then transferred it to a fictional repairer. The transfer left the supply at one.

Change one fact and ask what the rule should do. Suppose the cook had already set aside a portion for that diner. Does that change the award? What other benefit might River's action have created? An uncertain answer can stay open.

## Reproduce the local experiment

The [Python program](trial.py) and its tests use Python 3 and SQLite. Each local ledger starts empty. In a checkout of this repository, run:

```sh
python3 -m unittest -v
python3 trial.py propose lunch-01 River "A fictional diner received one additional meal after the kitchen ran out."
python3 trial.py review r1 lunch-01 researcher supported "One extra serving filled the outstanding request."
python3 trial.py review r2 lunch-01 reviewer supported "The second report describes that same serving."
python3 trial.py mint lunch-01
python3 trial.py transfer repair-01 River Repairer 1
python3 trial.py show
```

The example uses a fictional case, an experimental rate of one unit per additional meal, and a cap of ten units. A new researcher can reproduce it with a separate SQLite file using `--ledger PATH` before the command. Local copies have independent balances. HVT community accounts and their ledger are operated separately on the project website.

[Published formulas, source data and the first experiment](https://humanvaluetoken.org/research/v1)
