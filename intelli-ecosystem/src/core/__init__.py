"""
Intelli-EcoSystem Core Module
=============================

The core module provides the foundational components for the Intelli-EcoSystem,
including cognitive entity management, dimensional operations, and uiRSFS/iQNSH
integration.

Components:
    - DimensionalCoordinates: 7-dimensional position tracking
    - CognitiveEntity: Core entity class with full cognitive capabilities
    - RecursiveFeedbackLoop: uiRSFS implementation
    - iQNSHProcessor: Quantum-neural processing engine
    - DimensionalOperations: Cross-dimensional operations
"""

from .dimensional import DimensionalCoordinates, DimensionalOperations
from .entity import CognitiveEntity, CognitiveClass
from .uirsfs import RecursiveFeedbackLoop, ObservationLayer, AnalysisLayer, SynthesisLayer, EvolutionLayer
from .iqnsh import iQNSHProcessor, QuantumLayer, NeuralLayer, SyntheticLayer, HyperStructure

__version__ = "1.0.0"
__author__ = "Intelli-EcoSystem Team"

__all__ = [
    "DimensionalCoordinates",
    "DimensionalOperations",
    "CognitiveEntity",
    "CognitiveClass",
    "RecursiveFeedbackLoop",
    "ObservationLayer",
    "AnalysisLayer",
    "SynthesisLayer",
    "EvolutionLayer",
    "iQNSHProcessor",
    "QuantumLayer",
    "NeuralLayer",
    "SyntheticLayer",
    "HyperStructure",
]
