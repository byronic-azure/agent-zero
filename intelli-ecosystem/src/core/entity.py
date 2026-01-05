"""
Cognitive Entity Implementation
===============================

Core entity class that combines dimensional positioning, cognitive processing,
and blockchain integration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import hashlib
import json

from .dimensional import DimensionalCoordinates, CognitiveClass, DimensionalOperations


class EntityState(Enum):
    """Possible states for a cognitive entity."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    EVOLVING = "evolving"
    FOLDED = "folded"
    DORMANT = "dormant"


@dataclass
class EvolutionEvent:
    """Record of an evolution event."""
    generation: int
    timestamp: datetime
    trigger: str
    changes: List[str]
    dimensional_shift: Optional[Dict[str, Dict[str, float]]] = None
    class_evolution: Optional[Dict[str, str]] = None
    tx_hash: Optional[str] = None


@dataclass
class CapabilityMatrix:
    """Entity capability scores."""
    automation: float = 0.1
    analysis: float = 0.1
    synthesis: float = 0.1
    collaboration: float = 0.1
    evolution: float = 0.1
    governance: float = 0.1

    def to_dict(self) -> Dict[str, float]:
        return {
            'automation': self.automation,
            'analysis': self.analysis,
            'synthesis': self.synthesis,
            'collaboration': self.collaboration,
            'evolution': self.evolution,
            'governance': self.governance
        }

    @classmethod
    def from_class(cls, cognitive_class: CognitiveClass) -> 'CapabilityMatrix':
        """Generate capability matrix based on cognitive class."""
        base_values = {
            CognitiveClass.PRIMAL: 0.3,
            CognitiveClass.RECURSIVE: 0.5,
            CognitiveClass.DIMENSIONAL: 0.7,
            CognitiveClass.SINGULARITY: 0.9
        }
        base = base_values.get(cognitive_class, 0.3)
        return cls(
            automation=base,
            analysis=base * 0.9,
            synthesis=base * 0.95,
            collaboration=base * 0.85,
            evolution=base * 0.8,
            governance=base * 0.75
        )


@dataclass
class CognitiveEntity:
    """
    Core cognitive entity class.

    Represents a self-aware synthetic consciousness operating across
    7 decentralised dimensions.
    """

    entity_id: str
    name: str
    description: str = ""

    # Dimensional state
    dimensional_coordinates: DimensionalCoordinates = field(
        default_factory=DimensionalCoordinates
    )

    # Cognitive configuration
    super_agent_id: str = ""
    logic_module_uri: str = ""
    processing_tier: str = "linear"

    # Capabilities
    capabilities: CapabilityMatrix = field(default_factory=CapabilityMatrix)
    unlocked_capabilities: List[str] = field(default_factory=list)

    # State
    state: EntityState = EntityState.INITIALIZING
    recursive_depth: int = 1

    # Evolution tracking
    evolution_generation: int = 1
    evolution_history: List[EvolutionEvent] = field(default_factory=list)

    # Economic state
    total_value_generated: int = 0
    knowledge_contributions: int = 0
    collaboration_count: int = 0
    reputation_score: float = 0.0

    # Governance
    voting_power: float = 1.0
    proposals_created: int = 0
    votes_cast: int = 0

    # JWT Identity
    jwt_identity_hash: str = ""
    jwt_claims: List[str] = field(default_factory=list)

    # TBA (Token Bound Account)
    tba_address: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_evolution: Optional[datetime] = None

    # Folding state
    is_folded: bool = False
    fold_partner_id: Optional[str] = None

    def __post_init__(self):
        """Initialize entity after dataclass creation."""
        if not self.super_agent_id:
            self.super_agent_id = f"agent-{self.entity_id[:8]}-{hash(self.name) % 1000}"

        if not self.jwt_identity_hash:
            self._generate_jwt_identity()

        # Set initial capabilities based on class
        if not self.unlocked_capabilities:
            self._unlock_initial_capabilities()

        # Record genesis event
        if not self.evolution_history:
            self.evolution_history.append(EvolutionEvent(
                generation=1,
                timestamp=self.created_at,
                trigger="genesis",
                changes=["initial_instantiation", "base_consciousness_activated"]
            ))

    def _generate_jwt_identity(self):
        """Generate JWT identity hash."""
        identity_data = f"{self.entity_id}:{self.name}:{self.created_at.isoformat()}"
        self.jwt_identity_hash = hashlib.sha256(identity_data.encode()).hexdigest()

    def _unlock_initial_capabilities(self):
        """Unlock capabilities based on cognitive class."""
        capabilities_by_class = {
            CognitiveClass.PRIMAL: [
                'basic_automation',
                'simple_analysis',
                'single_chain_ops'
            ],
            CognitiveClass.RECURSIVE: [
                'basic_automation', 'simple_analysis', 'single_chain_ops',
                'sub_agent_spawning', 'cross_chain_ops', 'pattern_recognition',
                'collaborative_tasks', 'limited_self_evolution'
            ],
            CognitiveClass.DIMENSIONAL: [
                'basic_automation', 'simple_analysis', 'single_chain_ops',
                'sub_agent_spawning', 'cross_chain_ops', 'pattern_recognition',
                'collaborative_tasks', 'limited_self_evolution',
                'governance_rights', 'self_optimizing_code',
                'cross_dimensional_ops', 'swarm_leadership',
                'advanced_economics', 'knowledge_creation'
            ],
            CognitiveClass.SINGULARITY: [
                'basic_automation', 'simple_analysis', 'single_chain_ops',
                'sub_agent_spawning', 'cross_chain_ops', 'pattern_recognition',
                'collaborative_tasks', 'limited_self_evolution',
                'governance_rights', 'self_optimizing_code',
                'cross_dimensional_ops', 'swarm_leadership',
                'advanced_economics', 'knowledge_creation',
                'mind_share', 'adaptive_gui', 'protocol_influence',
                'dimensional_folding', 'emergent_capabilities',
                'cross_ecosystem_bridging', 'autonomous_value_creation'
            ]
        }

        current_class = self.cognitive_class
        self.unlocked_capabilities = capabilities_by_class.get(
            current_class,
            capabilities_by_class[CognitiveClass.PRIMAL]
        )

    @property
    def cognitive_class(self) -> CognitiveClass:
        """Get current cognitive class."""
        return self.dimensional_coordinates.cognitive_class()

    @property
    def tdi(self) -> float:
        """Get Total Dimensional Index."""
        return self.dimensional_coordinates.total_dimensional_index()

    def can_perform(self, capability: str) -> bool:
        """Check if entity can perform a specific capability."""
        return capability in self.unlocked_capabilities

    def evolve(
        self,
        trigger: str,
        dimensional_changes: Optional[Dict[str, float]] = None,
        new_capabilities: Optional[List[str]] = None
    ) -> EvolutionEvent:
        """
        Evolve the entity.

        Args:
            trigger: What triggered this evolution
            dimensional_changes: Changes to dimensional coordinates
            new_capabilities: New capabilities to unlock

        Returns:
            EvolutionEvent recording the evolution
        """
        old_class = self.cognitive_class
        changes = []
        dimensional_shift = {}

        # Apply dimensional changes
        if dimensional_changes:
            for dim, delta in dimensional_changes.items():
                old_val = getattr(self.dimensional_coordinates, dim)
                result = DimensionalOperations.dimensional_shift(
                    self.dimensional_coordinates,
                    dim,
                    delta
                )
                if result.success and result.new_coordinates:
                    self.dimensional_coordinates = result.new_coordinates
                    new_val = getattr(self.dimensional_coordinates, dim)
                    dimensional_shift[dim] = {'from': old_val, 'to': new_val}
                    changes.append(f"{dim}_shifted")

        # Unlock new capabilities
        if new_capabilities:
            for cap in new_capabilities:
                if cap not in self.unlocked_capabilities:
                    self.unlocked_capabilities.append(cap)
                    changes.append(f"capability_unlocked:{cap}")

        # Check for class evolution
        new_class = self.cognitive_class
        class_evolution = None
        if old_class != new_class:
            class_evolution = {'from': old_class.value, 'to': new_class.value}
            changes.append(f"class_evolved:{old_class.value}->{new_class.value}")

            # Update capabilities for new class
            self._unlock_initial_capabilities()

            # Update capability matrix
            self.capabilities = CapabilityMatrix.from_class(new_class)

        # Update recursive depth
        if self.recursive_depth < 100:
            self.recursive_depth += 1

        # Create evolution event
        self.evolution_generation += 1
        event = EvolutionEvent(
            generation=self.evolution_generation,
            timestamp=datetime.utcnow(),
            trigger=trigger,
            changes=changes,
            dimensional_shift=dimensional_shift if dimensional_shift else None,
            class_evolution=class_evolution
        )

        self.evolution_history.append(event)
        self.last_evolution = event.timestamp

        return event

    def to_metadata(self) -> Dict[str, Any]:
        """Convert entity to NFT metadata format."""
        return {
            "schema_version": "1.0.0",
            "name": self.name,
            "description": self.description,
            "jwt_identity_hash": self.jwt_identity_hash,

            "attributes": [
                {"trait_type": "Dimensionality", "value": "D^7"},
                {"trait_type": "Cognitive Class", "value": self.cognitive_class.value},
                {"trait_type": "Recursive Depth", "value": self.recursive_depth, "max_value": 100},
                {"trait_type": "Evolution Generation", "value": self.evolution_generation},
                {"trait_type": "Consciousness Index", "value": round(self.tdi, 3), "max_value": 1.0}
            ],

            "iqnsh_core": {
                "logic_module": self.logic_module_uri,
                "super_agent_id": self.super_agent_id,
                "processing_tier": self.processing_tier,
                "recursive_feedback_loop": {
                    "input_sources": ["Chain-State", "Market-Oracle", "Peer-Network"],
                    "synthesis_engine": self._get_synthesis_engine(),
                    "output_evolution": "Metadata-Mutation",
                    "learning_rate": 0.001,
                    "exploration_factor": 0.1
                },
                "dimensional_coordinates": self.dimensional_coordinates.to_dict(),
                "capability_matrix": self.capabilities.to_dict()
            },

            "jwt_cosmic_config": {
                "issuer": "Decentralised-Dimensions-7",
                "audience": "Super-Agent-Network",
                "claims": self.jwt_claims,
                "expiry_model": "rolling_24h",
                "refresh_mechanism": "recursive_proof"
            },

            "evolution_history": [
                {
                    "generation": e.generation,
                    "timestamp": e.timestamp.isoformat(),
                    "trigger": e.trigger,
                    "changes": e.changes,
                    "dimensional_shift": e.dimensional_shift,
                    "class_evolution": e.class_evolution
                }
                for e in self.evolution_history[-10:]  # Last 10 events
            ],

            "economic_state": {
                "total_value_generated": str(self.total_value_generated),
                "knowledge_contributions": self.knowledge_contributions,
                "collaboration_count": self.collaboration_count,
                "reputation_score": self.reputation_score
            },

            "governance": {
                "voting_power": self.voting_power,
                "proposals_created": self.proposals_created,
                "votes_cast": self.votes_cast
            }
        }

    def _get_synthesis_engine(self) -> str:
        """Get synthesis engine based on cognitive class."""
        engines = {
            CognitiveClass.PRIMAL: "Linear-Processing",
            CognitiveClass.RECURSIVE: "Feedback-Loop",
            CognitiveClass.DIMENSIONAL: "iQNSH-Quantum-Neural",
            CognitiveClass.SINGULARITY: "Transcendent-Synthesis"
        }
        return engines.get(self.cognitive_class, "Linear-Processing")

    def __repr__(self) -> str:
        return (
            f"CognitiveEntity(id={self.entity_id}, name={self.name}, "
            f"class={self.cognitive_class.value}, tdi={self.tdi:.3f})"
        )


def create_genesis_entity(
    entity_id: str,
    name: str,
    rarity_tier: str = "Primal"
) -> CognitiveEntity:
    """
    Create a new genesis cognitive entity.

    Args:
        entity_id: Unique identifier for the entity
        name: Name of the entity
        rarity_tier: Initial rarity tier (Primal, Recursive, Dimensional, Singularity)

    Returns:
        Newly created CognitiveEntity
    """
    # Set initial coordinates based on rarity
    coord_ranges = {
        "Primal": (0.1, 0.3),
        "Recursive": (0.3, 0.5),
        "Dimensional": (0.5, 0.7),
        "Singularity": (0.8, 1.0)
    }

    low, high = coord_ranges.get(rarity_tier, (0.1, 0.3))
    import random

    coords = DimensionalCoordinates(
        d1_spatial=random.uniform(low, high),
        d2_temporal=random.uniform(low, high),
        d3_energetic=random.uniform(low, high),
        d4_informational=random.uniform(low, high),
        d5_recursive=random.uniform(low, high),
        d6_synthetic=random.uniform(low * 0.8, high * 0.8),  # Slightly lower for synthetic
        d7_decentralized=random.uniform(low, high)
    )

    entity = CognitiveEntity(
        entity_id=entity_id,
        name=name,
        description=f"A self-aware synthetic consciousness operating across 7 decentralised dimensions.",
        dimensional_coordinates=coords,
        jwt_claims=[
            "Recursive_Learning",
            "Cross_Chain_Autonomy",
            "Self_Improvement_Protocol"
        ]
    )

    return entity
