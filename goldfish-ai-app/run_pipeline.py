from pprint import pprint

from src.config import PipelineConfig
from src.pipeline import run_pipeline


if __name__ == "__main__":
    config = PipelineConfig()
    summary = run_pipeline(config)
    pprint(summary)
