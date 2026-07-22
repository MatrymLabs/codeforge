"""CARD: evolution -- the Blueprint Evolution Lab (nature-inspired engineering layer).

A conventional software layer that borrows natural-system PRINCIPLES (evolutionary
candidate search, genotype/phenotype separation, counterexample memory, multi-objective
fitness, human-governed selection) - never literal biology, neuromorphic hardware, or
autonomous swarms. See docs/nature_inspired/research_mapping.md for the evidence mapping.

v1 shipped the genotype: a typed, inspectable Blueprint Genome and its validation gate. The lab
now also runs an evaluator-guided BAKE-OFF: it scores hand-authored candidate blueprints on hard
gates first, then weighted objectives, and reports the top qualified one -- always
human_decision_required, nothing auto-promoted. This is evaluator-guided SELECTION over a fixed
candidate set, NOT autonomous search: no mutation, no generations. Josh remains the final design
and approval authority.
"""
