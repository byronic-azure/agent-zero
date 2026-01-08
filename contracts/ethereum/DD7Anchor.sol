// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title DD7Anchor
 * @notice Sovereign-grade blockchain anchoring for DD7 attestation proofs
 * @dev Stores Merkle roots and ZK proof commitments on Ethereum
 *
 * Architecture:
 * - Immutable anchor records linked by previous hash
 * - ZK proof verification using Groth16 (BN254)
 * - Multi-cluster support with access control
 * - Event emission for off-chain indexing
 */

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract DD7Anchor is AccessControl, ReentrancyGuard, Pausable {
    // ==========================================================================
    // ROLES
    // ==========================================================================
    bytes32 public constant ANCHOR_ROLE = keccak256("ANCHOR_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    // ==========================================================================
    // STRUCTS
    // ==========================================================================
    struct AnchorRecord {
        bytes32 merkleRoot;
        bytes32 clusterID;
        bytes32 previousAnchor;
        uint256 timestamp;
        uint256 blockNumber;
        uint256 batchSize;
        bytes32 proofCommitment;
        address submitter;
    }

    struct ClusterConfig {
        bool active;
        uint256 anchorCount;
        bytes32 latestAnchor;
        uint256 minAnchorInterval;
        uint256 lastAnchorTime;
    }

    // ==========================================================================
    // STATE
    // ==========================================================================
    mapping(bytes32 => AnchorRecord) public anchors;
    mapping(bytes32 => ClusterConfig) public clusters;
    mapping(bytes32 => bool) public usedMerkleRoots;

    bytes32[] public anchorHistory;
    uint256 public totalAnchors;

    // Groth16 verifier contract (deployed separately)
    address public zkVerifier;

    // ==========================================================================
    // EVENTS
    // ==========================================================================
    event AnchorCreated(
        bytes32 indexed anchorHash,
        bytes32 indexed clusterID,
        bytes32 merkleRoot,
        uint256 timestamp,
        uint256 batchSize
    );

    event ClusterRegistered(
        bytes32 indexed clusterID,
        uint256 minAnchorInterval
    );

    event ClusterDeactivated(bytes32 indexed clusterID);

    event ProofVerified(
        bytes32 indexed anchorHash,
        bytes32 proofCommitment,
        bool valid
    );

    // ==========================================================================
    // CONSTRUCTOR
    // ==========================================================================
    constructor(address _zkVerifier) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(ANCHOR_ROLE, msg.sender);
        _grantRole(VERIFIER_ROLE, msg.sender);

        zkVerifier = _zkVerifier;
    }

    // ==========================================================================
    // CLUSTER MANAGEMENT
    // ==========================================================================

    /**
     * @notice Register a new cluster for anchoring
     * @param clusterID Unique identifier for the cluster
     * @param minAnchorInterval Minimum seconds between anchors
     */
    function registerCluster(
        bytes32 clusterID,
        uint256 minAnchorInterval
    ) external onlyRole(ADMIN_ROLE) {
        require(!clusters[clusterID].active, "Cluster already registered");
        require(minAnchorInterval >= 60, "Interval too short"); // Min 1 minute

        clusters[clusterID] = ClusterConfig({
            active: true,
            anchorCount: 0,
            latestAnchor: bytes32(0),
            minAnchorInterval: minAnchorInterval,
            lastAnchorTime: 0
        });

        emit ClusterRegistered(clusterID, minAnchorInterval);
    }

    /**
     * @notice Deactivate a cluster
     * @param clusterID Cluster to deactivate
     */
    function deactivateCluster(bytes32 clusterID) external onlyRole(ADMIN_ROLE) {
        require(clusters[clusterID].active, "Cluster not active");
        clusters[clusterID].active = false;
        emit ClusterDeactivated(clusterID);
    }

    // ==========================================================================
    // ANCHORING
    // ==========================================================================

    /**
     * @notice Submit a new anchor record
     * @param clusterID Cluster submitting the anchor
     * @param merkleRoot Root of the Merkle tree containing proofs
     * @param batchSize Number of proofs in this batch
     * @param proofCommitment Hash of the ZK proof data
     * @return anchorHash The hash identifying this anchor
     */
    function anchor(
        bytes32 clusterID,
        bytes32 merkleRoot,
        uint256 batchSize,
        bytes32 proofCommitment
    ) external nonReentrant whenNotPaused onlyRole(ANCHOR_ROLE) returns (bytes32 anchorHash) {
        ClusterConfig storage cluster = clusters[clusterID];

        require(cluster.active, "Cluster not active");
        require(!usedMerkleRoots[merkleRoot], "Merkle root already anchored");
        require(batchSize > 0, "Batch size must be positive");
        require(
            block.timestamp >= cluster.lastAnchorTime + cluster.minAnchorInterval,
            "Anchor interval not met"
        );

        // Compute anchor hash
        anchorHash = keccak256(abi.encodePacked(
            merkleRoot,
            clusterID,
            cluster.latestAnchor,
            block.timestamp,
            block.number,
            batchSize,
            proofCommitment
        ));

        // Store anchor record
        anchors[anchorHash] = AnchorRecord({
            merkleRoot: merkleRoot,
            clusterID: clusterID,
            previousAnchor: cluster.latestAnchor,
            timestamp: block.timestamp,
            blockNumber: block.number,
            batchSize: batchSize,
            proofCommitment: proofCommitment,
            submitter: msg.sender
        });

        // Update state
        usedMerkleRoots[merkleRoot] = true;
        cluster.latestAnchor = anchorHash;
        cluster.anchorCount++;
        cluster.lastAnchorTime = block.timestamp;
        anchorHistory.push(anchorHash);
        totalAnchors++;

        emit AnchorCreated(
            anchorHash,
            clusterID,
            merkleRoot,
            block.timestamp,
            batchSize
        );

        return anchorHash;
    }

    // ==========================================================================
    // VERIFICATION
    // ==========================================================================

    /**
     * @notice Verify a Merkle proof against an anchored root
     * @param anchorHash The anchor containing the Merkle root
     * @param leaf The leaf to verify
     * @param proof The Merkle proof path
     * @param index The leaf index
     * @return valid True if the proof is valid
     */
    function verifyMerkleProof(
        bytes32 anchorHash,
        bytes32 leaf,
        bytes32[] calldata proof,
        uint256 index
    ) external view returns (bool valid) {
        AnchorRecord storage record = anchors[anchorHash];
        require(record.timestamp > 0, "Anchor not found");

        bytes32 computedHash = leaf;

        for (uint256 i = 0; i < proof.length; i++) {
            if (index % 2 == 0) {
                computedHash = keccak256(abi.encodePacked(computedHash, proof[i]));
            } else {
                computedHash = keccak256(abi.encodePacked(proof[i], computedHash));
            }
            index = index / 2;
        }

        return computedHash == record.merkleRoot;
    }

    /**
     * @notice Verify a ZK proof using the external verifier
     * @param anchorHash The anchor to verify against
     * @param proof The Groth16 proof data
     * @param publicInputs The public inputs to the circuit
     * @return valid True if the proof is valid
     */
    function verifyZKProof(
        bytes32 anchorHash,
        bytes calldata proof,
        uint256[] calldata publicInputs
    ) external onlyRole(VERIFIER_ROLE) returns (bool valid) {
        AnchorRecord storage record = anchors[anchorHash];
        require(record.timestamp > 0, "Anchor not found");

        // Call external verifier contract
        (bool success, bytes memory result) = zkVerifier.staticcall(
            abi.encodeWithSignature(
                "verify(bytes,uint256[])",
                proof,
                publicInputs
            )
        );

        valid = success && abi.decode(result, (bool));

        emit ProofVerified(anchorHash, record.proofCommitment, valid);

        return valid;
    }

    // ==========================================================================
    // QUERIES
    // ==========================================================================

    /**
     * @notice Get the anchor chain for a cluster
     * @param clusterID The cluster to query
     * @param count Number of anchors to return (0 for all)
     * @return hashes Array of anchor hashes (most recent first)
     */
    function getAnchorChain(
        bytes32 clusterID,
        uint256 count
    ) external view returns (bytes32[] memory hashes) {
        ClusterConfig storage cluster = clusters[clusterID];

        if (count == 0 || count > cluster.anchorCount) {
            count = cluster.anchorCount;
        }

        hashes = new bytes32[](count);
        bytes32 current = cluster.latestAnchor;

        for (uint256 i = 0; i < count && current != bytes32(0); i++) {
            hashes[i] = current;
            current = anchors[current].previousAnchor;
        }

        return hashes;
    }

    /**
     * @notice Get full anchor record
     * @param anchorHash The anchor hash
     * @return record The full anchor record
     */
    function getAnchor(bytes32 anchorHash) external view returns (AnchorRecord memory record) {
        return anchors[anchorHash];
    }

    /**
     * @notice Get cluster configuration
     * @param clusterID The cluster ID
     * @return config The cluster configuration
     */
    function getCluster(bytes32 clusterID) external view returns (ClusterConfig memory config) {
        return clusters[clusterID];
    }

    // ==========================================================================
    // ADMIN
    // ==========================================================================

    /**
     * @notice Update the ZK verifier contract address
     * @param newVerifier New verifier contract address
     */
    function setZKVerifier(address newVerifier) external onlyRole(ADMIN_ROLE) {
        require(newVerifier != address(0), "Invalid address");
        zkVerifier = newVerifier;
    }

    /**
     * @notice Pause anchoring (emergency)
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause anchoring
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }
}
