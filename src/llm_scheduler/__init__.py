"""OS-inspired scheduling of LLM inference requests: a discrete-event simulation study."""

from .policies import AgingSJFPolicy, FCFSPolicy, PredictiveSJFPolicy, build_policy
from .predictor import HeuristicPredictor, build_predictor
from .request import PromptFeatures, Request, RequestSpec, RequestState
from .service_model import ServiceModel
from .simulator import SimulationResult, Simulator
from .workload import Workload, generate_workload, workload_from_rows

__version__ = "0.5.0"

__all__ = [
    "AgingSJFPolicy",
    "FCFSPolicy",
    "PredictiveSJFPolicy",
    "build_policy",
    "HeuristicPredictor",
    "build_predictor",
    "PromptFeatures",
    "Request",
    "RequestSpec",
    "RequestState",
    "ServiceModel",
    "SimulationResult",
    "Simulator",
    "Workload",
    "generate_workload",
    "workload_from_rows",
]
