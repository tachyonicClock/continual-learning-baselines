#!/usr/bin/env python3
import numpy as np
import torch
import torchvision.transforms as transforms
from torch.optim import SGD

from avalanche.benchmarks.classic import SplitCIFAR10
from avalanche.benchmarks.generators import benchmark_with_validation_stream
from avalanche.benchmarks.scenarios.online_scenario import OnlineCLScenario
from avalanche.evaluation.metrics import accuracy_metrics, loss_metrics
from avalanche.logging import InteractiveLogger
from avalanche.models import SlimResNet18
from avalanche.models.dynamic_modules import IncrementalClassifier
from avalanche.training.plugins import EvaluationPlugin
from avalanche.training.supervised import OnlineNaive, ER_ACE
from experiments.utils import create_default_args, set_seed


def erace_scifar10(override_args=None):
    args = create_default_args(
        {
            "cuda": 0,
            "mem_size": 1000,
            "lr": 0.1,
            "train_mb_size": 10,
            "seed": None,
            "batch_size_mem": 10,
        },
        override_args
    )
    set_seed(args.seed)
    fixed_class_order = np.arange(10)
    device = torch.device(
        f"cuda:{args.cuda}" if torch.cuda.is_available() and args.cuda >= 0 else "cpu"
    )

    unique_transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                (0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)
            ),
        ]
    )
    
    scenario = SplitCIFAR10(
        5,
        return_task_id=False,
        seed=0,
        fixed_class_order=fixed_class_order,
        shuffle=True,
        class_ids_from_zero_in_each_exp=False,
        train_transform=unique_transform,
        eval_transform=unique_transform,
    )

    input_size = (3, 32, 32)
    model = SlimResNet18(1)
    model.linear = IncrementalClassifier(model.linear.in_features, 1)
    optimizer = SGD(model.parameters(), lr=args.lr)
    interactive_logger = InteractiveLogger()
    loggers = [interactive_logger]
    training_metrics = []
    evaluation_metrics = [
        accuracy_metrics(epoch=True, stream=True),
        loss_metrics(epoch=True, stream=True),
    ]
    evaluator = EvaluationPlugin(
        *training_metrics,
        *evaluation_metrics,
        loggers=loggers,
    )
    plugins = []
    cl_strategy = ER_ACE(
        model=model,
        optimizer=optimizer,
        plugins=plugins,
        evaluator=evaluator,
        device=device,
        train_mb_size=args.train_mb_size,
        eval_mb_size=64,
        mem_size=args.mem_size,
        batch_size_mem=args.batch_size_mem,
    )
    for t, experience in enumerate(scenario.train_stream):
        cl_strategy.train(
            experience,
            num_workers=0,
            drop_last=True,
        )
        cl_strategy.eval(scenario.test_stream[: t + 1])
    results = cl_strategy.eval(scenario.test_stream)
    return results


if __name__ == "__main__":
    res = erace_scifar10()
    print(res)
