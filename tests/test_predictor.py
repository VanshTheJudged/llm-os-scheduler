import inspect

import pytest

from llm_scheduler.predictor import (
    HeuristicPredictor,
    MaxTokensPredictor,
    NoisyOraclePredictor,
    OraclePredictor,
    PromptLengthPredictor,
    RandomPredictor,
    build_predictor,
)
from llm_scheduler.request import PromptFeatures, RequestSpec


def feats(task="chat", prompt=100, detail=False, max_tokens=4096, rid=0):
    return PromptFeatures(rid, prompt, task, detail, max_tokens)


def test_heuristic_uses_only_observable_features():
    p = HeuristicPredictor()
    f = feats("code")
    a = RequestSpec(f, 0.0, actual_output_tokens=3)
    b = RequestSpec(f, 0.0, actual_output_tokens=3000)
    assert p.predict(a.features) == p.predict(b.features)
    assert list(inspect.signature(p.predict).parameters) == ["features"]
    assert p.uses_ground_truth is False


def test_heuristic_rules():
    p = HeuristicPredictor()
    assert p.predict(feats("qa")) == 32
    assert p.predict(feats("longform")) == 512
    assert p.predict(feats("longform", detail=True)) == 1024
    assert p.predict(feats("longform", detail=True, max_tokens=512)) == 512  # clipped to cap
    assert p.predict(feats("summarization", prompt=1024)) == 128
    assert p.predict(feats("summarization", prompt=4096)) == 256  # sqrt(4) x 128
    assert p.predict(feats("unknown_task")) == 128  # default prior


def test_naive_baselines():
    assert PromptLengthPredictor().predict(feats(prompt=300)) == 300
    assert PromptLengthPredictor().predict(feats(prompt=9000, max_tokens=1024)) == 1024
    assert MaxTokensPredictor().predict(feats(max_tokens=2048)) == 2048


def test_oracle_is_flagged_reference():
    o = OraclePredictor({0: 17, 1: 400})
    assert o.uses_ground_truth is True
    assert o.predict(feats(rid=1)) == 400


def test_noisy_oracle_sigma_zero_equals_oracle_and_is_deterministic():
    truth = {i: 10 * (i + 1) for i in range(50)}
    z = NoisyOraclePredictor(truth, sigma=0.0, seed=3)
    assert all(z.predict(feats(rid=i)) == truth[i] for i in truth)
    n1 = NoisyOraclePredictor(truth, sigma=0.5, seed=3)
    n2 = NoisyOraclePredictor(truth, sigma=0.5, seed=3)
    forward = [n1.predict(feats(rid=i)) for i in truth]
    backward = [n2.predict(feats(rid=i)) for i in reversed(list(truth))][::-1]
    assert forward == backward  # independent of call order
    assert forward != [truth[i] for i in truth]
    assert all(v >= 1 for v in forward)


def test_random_predictor_range_and_determinism():
    r1, r2 = RandomPredictor(seed=1, upper=100), RandomPredictor(seed=1, upper=100)
    vals = [r1.predict(feats(rid=i)) for i in range(500)]
    assert vals == [r2.predict(feats(rid=i)) for i in range(500)]
    assert min(vals) >= 1 and max(vals) <= 100
    assert len(set(vals)) > 50


def test_build_predictor():
    assert build_predictor(None, {}, 0) is None
    assert isinstance(build_predictor({"type": "heuristic"}, {}, 0), HeuristicPredictor)
    assert build_predictor({"type": "noisy_oracle", "sigma": 0.25}, {0: 5}, 0).sigma == 0.25
    with pytest.raises(KeyError):
        build_predictor({"type": "nope"}, {}, 0)
