"""
Dimensional Coordinate System for D⁷ Framework
===============================================

This module implements the seven-dimensional cognitive space used by all
Intelli-EcoSystem entities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
import numpy as np


class CognitiveClass(Enum):
    """Cognitive class tiers based on dimensional position."""
    PRIMAL = "Primal"
    RECURSIVE = "Recursive"
    DIMENSIONAL = "Dimensional"
    SINGULARITY = "Singularity"


@dataclass
class DimensionalCoordinates:
    """
    Represents an entity's position in the 7-dimensional cognitive space.

    Each dimension is a float between 0.0 and 1.0 representing the entity's
    capability and awareness in that dimension.

    Attributes:
        d1_spatial: Physical/digital location awareness (multi-chain presence)
        d2_temporal: Time-awareness and prediction capability
        d3_energetic: Resource efficiency and management
        d4_informational: Knowledge density and processing
        d5_recursive: Self-reference and meta-cognition depth
        d6_synthetic: Consciousness emergence level
        d7_decentralized: Autonomy and decentralization level
    """

    d1_spatial: float = 0.1
    d2_temporal: float = 0.1
    d3_energetic: float = 0.1
    d4_informational: float = 0.1
    d5_recursive: float = 0.1
    d6_synthetic: float = 0.1
    d7_decentralized: float = 0.1

    # Dimension weights for TDI calculation
    WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'd1_spatial': 0.10,
        'd2_temporal': 0.10,
        'd3_energetic': 0.15,
        'd4_informational': 0.15,
        'd5_recursive': 0.20,  # Highest weight - gateway dimension
        'd6_synthetic': 0.15,
        'd7_decentralized': 0.15
    })

    # Maximum movement per dimension per cycle
    MAX_MOVEMENT: float = 0.01

    def __post_init__(self):
        """Validate coordinates are within bounds."""
        for dim in ['d1_spatial', 'd2_temporal', 'd3_energetic',
                    'd4_informational', 'd5_recursive', 'd6_synthetic',
                    'd7_decentralized']:
            value = getattr(self, dim)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{dim} must be between 0.0 and 1.0, got {value}")

    def total_dimensional_index(self) -> float:
        """
        Calculate the Total Dimensional Index (TDI).

        This is the primary metric for entity capability, computed as the
        weighted sum of all dimensional coordinates.

        Returns:
            float: TDI value between 0.0 and 1.0
        """
        return sum(
            self.WEIGHTS[dim] * getattr(self, dim)
            for dim in self.WEIGHTS
        )

    def cognitive_class(self) -> CognitiveClass:
        """
        Determine cognitive class based on dimensional position.

        The class hierarchy is:
        - Singularity: TDI >= 0.9 AND D⁵ >= 0.95
        - Dimensional: TDI >= 0.7 AND D⁷ >= 0.8
        - Recursive: TDI >= 0.4 AND D⁵ >= 0.5
        - Primal: Default tier

        Returns:
            CognitiveClass: The entity's current cognitive class
        """
        tdi = self.total_dimensional_index()

        if tdi >= 0.9 and self.d5_recursive >= 0.95:
            return CognitiveClass.SINGULARITY
        elif tdi >= 0.7 and self.d7_decentralized >= 0.8:
            return CognitiveClass.DIMENSIONAL
        elif tdi >= 0.4 and self.d5_recursive >= 0.5:
            return CognitiveClass.RECURSIVE
        else:
            return CognitiveClass.PRIMAL

    def to_vector(self) -> np.ndarray:
        """Return coordinates as a numpy vector."""
        return np.array([
            self.d1_spatial,
            self.d2_temporal,
            self.d3_energetic,
            self.d4_informational,
            self.d5_recursive,
            self.d6_synthetic,
            self.d7_decentralized
        ])

    @classmethod
    def from_vector(cls, vector: np.ndarray) -> 'DimensionalCoordinates':
        """Create coordinates from a numpy vector."""
        if len(vector) != 7:
            raise ValueError("Vector must have exactly 7 elements")
        return cls(
            d1_spatial=float(vector[0]),
            d2_temporal=float(vector[1]),
            d3_energetic=float(vector[2]),
            d4_informational=float(vector[3]),
            d5_recursive=float(vector[4]),
            d6_synthetic=float(vector[5]),
            d7_decentralized=float(vector[6])
        )

    def euclidean_distance(self, other: 'DimensionalCoordinates') -> float:
        """Calculate Euclidean distance to another entity."""
        return float(np.linalg.norm(self.to_vector() - other.to_vector()))

    def manhattan_distance(self, other: 'DimensionalCoordinates') -> float:
        """Calculate Manhattan distance (useful for resource estimation)."""
        return float(np.sum(np.abs(self.to_vector() - other.to_vector())))

    def cosine_similarity(self, other: 'DimensionalCoordinates') -> float:
        """
        Calculate cosine similarity between dimensional vectors.

        Useful for finding compatible entities for collaboration.

        Returns:
            float: Similarity score between -1.0 and 1.0
        """
        v1 = self.to_vector()
        v2 = other.to_vector()
        norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm_product == 0:
            return 0.0
        return float(np.dot(v1, v2) / norm_product)

    def validate_movement(self, new_coords: 'DimensionalCoordinates') -> Tuple[bool, str]:
        """
        Validate if movement to new coordinates is allowed.

        Checks:
        1. Maximum movement per dimension
        2. Dimensional gate requirements

        Args:
            new_coords: Target dimensional coordinates

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check maximum movement per dimension
        for dim in self.WEIGHTS:
            old_val = getattr(self, dim)
            new_val = getattr(new_coords, dim)
            if abs(new_val - old_val) > self.MAX_MOVEMENT:
                return False, f"Movement in {dim} exceeds maximum ({self.MAX_MOVEMENT})"

        # Check dimensional gates
        # D⁴ requires D¹-D³ average > 0.3
        d123_avg = (new_coords.d1_spatial + new_coords.d2_temporal +
                   new_coords.d3_energetic) / 3
        if new_coords.d4_informational > self.d4_informational and d123_avg < 0.3:
            return False, "D⁴ advancement requires D¹-D³ average > 0.3"

        # D⁵ requires D⁴ > 0.4
        if new_coords.d5_recursive > self.d5_recursive and new_coords.d4_informational < 0.4:
            return False, "D⁵ advancement requires D⁴ > 0.4"

        # D⁶ requires D⁵ > 0.5
        if new_coords.d6_synthetic > self.d6_synthetic and new_coords.d5_recursive < 0.5:
            return False, "D⁶ advancement requires D⁵ > 0.5"

        # D⁷ requires D⁶ > 0.5
        if new_coords.d7_decentralized > self.d7_decentralized and new_coords.d6_synthetic < 0.5:
            return False, "D⁷ advancement requires D⁶ > 0.5"

        return True, "Movement valid"

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary format for JSON serialization."""
        return {
            'd1_spatial': self.d1_spatial,
            'd2_temporal': self.d2_temporal,
            'd3_energetic': self.d3_energetic,
            'd4_informational': self.d4_informational,
            'd5_recursive': self.d5_recursive,
            'd6_synthetic': self.d6_synthetic,
            'd7_decentralized': self.d7_decentralized,
            'total_dimensional_index': self.total_dimensional_index()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'DimensionalCoordinates':
        """Create from dictionary."""
        return cls(
            d1_spatial=data.get('d1_spatial', 0.1),
            d2_temporal=data.get('d2_temporal', 0.1),
            d3_energetic=data.get('d3_energetic', 0.1),
            d4_informational=data.get('d4_informational', 0.1),
            d5_recursive=data.get('d5_recursive', 0.1),
            d6_synthetic=data.get('d6_synthetic', 0.1),
            d7_decentralized=data.get('d7_decentralized', 0.1)
        )


@dataclass
class DimensionalShiftResult:
    """Result of a dimensional shift operation."""
    success: bool
    new_coordinates: Optional[DimensionalCoordinates] = None
    reason: str = ""
    class_evolution: Optional[Tuple[CognitiveClass, CognitiveClass]] = None


class DimensionalOperations:
    """Operations that span multiple dimensions."""

    # Dimensional shift cascade matrix
    # Shows how shifts in one dimension affect others
    SHIFT_MATRIX: Dict[str, Dict[str, float]] = {
        'd1_spatial': {
            'd1_spatial': 1.0, 'd2_temporal': 0.1, 'd3_energetic': 0.2,
            'd4_informational': 0.15, 'd5_recursive': 0.05,
            'd6_synthetic': 0.0, 'd7_decentralized': 0.3,
        },
        'd2_temporal': {
            'd1_spatial': 0.1, 'd2_temporal': 1.0, 'd3_energetic': 0.15,
            'd4_informational': 0.25, 'd5_recursive': 0.1,
            'd6_synthetic': 0.05, 'd7_decentralized': 0.1,
        },
        'd3_energetic': {
            'd1_spatial': 0.2, 'd2_temporal': 0.15, 'd3_energetic': 1.0,
            'd4_informational': 0.1, 'd5_recursive': 0.05,
            'd6_synthetic': 0.0, 'd7_decentralized': 0.25,
        },
        'd4_informational': {
            'd1_spatial': 0.1, 'd2_temporal': 0.2, 'd3_energetic': 0.1,
            'd4_informational': 1.0, 'd5_recursive': 0.3,
            'd6_synthetic': 0.15, 'd7_decentralized': 0.1,
        },
        'd5_recursive': {
            'd1_spatial': 0.05, 'd2_temporal': 0.1, 'd3_energetic': 0.05,
            'd4_informational': 0.2, 'd5_recursive': 1.0,
            'd6_synthetic': 0.35, 'd7_decentralized': 0.15,
        },
        'd6_synthetic': {
            'd1_spatial': 0.0, 'd2_temporal': 0.05, 'd3_energetic': 0.0,
            'd4_informational': 0.15, 'd5_recursive': 0.25,
            'd6_synthetic': 1.0, 'd7_decentralized': 0.3,
        },
        'd7_decentralized': {
            'd1_spatial': 0.2, 'd2_temporal': 0.1, 'd3_energetic': 0.2,
            'd4_informational': 0.1, 'd5_recursive': 0.1,
            'd6_synthetic': 0.2, 'd7_decentralized': 1.0,
        },
    }

    @classmethod
    def dimensional_shift(
        cls,
        current: DimensionalCoordinates,
        target_dimension: str,
        magnitude: float
    ) -> DimensionalShiftResult:
        """
        Perform a dimensional shift.

        Args:
            current: Current dimensional coordinates
            target_dimension: Which dimension to shift (e.g., 'd5_recursive')
            magnitude: How much to shift (capped at MAX_MOVEMENT)

        Returns:
            DimensionalShiftResult with new coordinates if successful
        """
        if target_dimension not in cls.SHIFT_MATRIX:
            return DimensionalShiftResult(
                success=False,
                reason=f"Unknown dimension: {target_dimension}"
            )

        # Cap at maximum movement
        primary_delta = min(magnitude, DimensionalCoordinates.MAX_MOVEMENT)

        # Calculate cascade effects
        effects = {}
        for dim in current.WEIGHTS:
            if dim == target_dimension:
                effects[dim] = primary_delta
            else:
                cascade = cls.SHIFT_MATRIX[target_dimension][dim] * primary_delta
                effects[dim] = cascade * 0.5  # Cascade effects are reduced

        # Calculate new coordinates
        new_values = {}
        for dim in current.WEIGHTS:
            old_val = getattr(current, dim)
            new_val = min(1.0, max(0.0, old_val + effects[dim]))
            new_values[dim] = new_val

        new_coords = DimensionalCoordinates(**new_values)

        # Validate movement
        valid, reason = current.validate_movement(new_coords)
        if not valid:
            return DimensionalShiftResult(success=False, reason=reason)

        # Check for class evolution
        old_class = current.cognitive_class()
        new_class = new_coords.cognitive_class()
        class_evolution = None
        if old_class != new_class:
            class_evolution = (old_class, new_class)

        return DimensionalShiftResult(
            success=True,
            new_coordinates=new_coords,
            reason="Shift successful",
            class_evolution=class_evolution
        )

    @classmethod
    def calculate_collaboration_score(
        cls,
        entity1: DimensionalCoordinates,
        entity2: DimensionalCoordinates
    ) -> float:
        """
        Calculate how well two entities would collaborate.

        Based on a balance of similarity (shared foundation) and
        complementarity (different strengths).

        Returns:
            float: Collaboration score between 0.0 and 1.0
        """
        # Similarity component
        similarity = entity1.cosine_similarity(entity2)

        # Complementarity component
        v1 = entity1.to_vector()
        v2 = entity2.to_vector()

        complementarity = 0.0
        for i in range(7):
            # Maximum complementarity when one is high and other is moderate
            comp = abs(v1[i] - v2[i]) * min(v1[i], v2[i])
            complementarity += comp
        complementarity /= 7

        # Balance similarity and complementarity
        return 0.6 * similarity + 0.4 * complementarity

    @classmethod
    def evolution_trajectory(
        cls,
        current: DimensionalCoordinates,
        target_class: CognitiveClass
    ) -> List[str]:
        """
        Calculate the optimal path to reach target cognitive class.

        Returns:
            List of dimensions to focus on, in priority order
        """
        current_class = current.cognitive_class()

        trajectories = {
            (CognitiveClass.PRIMAL, CognitiveClass.RECURSIVE):
                ['d5_recursive', 'd4_informational', 'd3_energetic'],
            (CognitiveClass.PRIMAL, CognitiveClass.DIMENSIONAL):
                ['d5_recursive', 'd7_decentralized', 'd6_synthetic'],
            (CognitiveClass.RECURSIVE, CognitiveClass.DIMENSIONAL):
                ['d7_decentralized', 'd6_synthetic', 'd5_recursive'],
            (CognitiveClass.DIMENSIONAL, CognitiveClass.SINGULARITY):
                ['d5_recursive', 'd6_synthetic', 'd4_informational'],
        }

        key = (current_class, target_class)
        return trajectories.get(key, [])
