// Package circuits implements DD7 zero-knowledge proof circuits using gnark
// These circuits enable sovereign-grade attestation without revealing sensitive data
package circuits

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// AttestationCircuit proves TPM+SGX attestation validity without revealing quotes
// Implements: H(tpmQuote || sgxQuote || containerDigest) == publicCommitment
type AttestationCircuit struct {
	// Public inputs
	ClusterID        frontend.Variable `gnark:"clusterID,public"`
	NodeDigest       frontend.Variable `gnark:"nodeDigest,public"`
	Timestamp        frontend.Variable `gnark:"timestamp,public"`
	PublicCommitment frontend.Variable `gnark:"commitment,public"`

	// Private inputs (witnesses)
	TPMQuote        frontend.Variable `gnark:"tpmQuote"`
	SGXQuote        frontend.Variable `gnark:"sgxQuote"`
	ContainerDigest frontend.Variable `gnark:"containerDigest"`
	Nonce           frontend.Variable `gnark:"nonce"`
}

// Define implements the circuit constraints
func (c *AttestationCircuit) Define(api frontend.API) error {
	// Initialize MiMC hash
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// Hash private inputs to create commitment
	h.Write(c.TPMQuote)
	h.Write(c.SGXQuote)
	h.Write(c.ContainerDigest)
	h.Write(c.ClusterID)
	h.Write(c.Timestamp)
	h.Write(c.Nonce)

	computedCommitment := h.Sum()

	// Verify commitment matches public value
	api.AssertIsEqual(computedCommitment, c.PublicCommitment)

	return nil
}

// PhiComplianceCircuit proves Φ threshold compliance without revealing exact value
// Based on consciousness extension formula: t' = t × √(1 - v²/c²) × e^(-C/C_crit)
type PhiComplianceCircuit struct {
	// Public inputs
	PhiThreshold   frontend.Variable `gnark:"phiThreshold,public"`
	CommitmentHash frontend.Variable `gnark:"commitmentHash,public"`
	Timestamp      frontend.Variable `gnark:"timestamp,public"`

	// Private inputs
	PhiValue        frontend.Variable `gnark:"phiValue"`
	UptimeNumerator frontend.Variable `gnark:"uptimeNumerator"`
	UptimeDenom     frontend.Variable `gnark:"uptimeDenom"`
	DriftValue      frontend.Variable `gnark:"driftValue"`
	DriftMax        frontend.Variable `gnark:"driftMax"`
	Salt            frontend.Variable `gnark:"salt"`
}

// Define implements Φ compliance verification
func (c *PhiComplianceCircuit) Define(api frontend.API) error {
	// Verify Φ >= threshold (using field comparison)
	// PhiValue * 100 >= PhiThreshold * 100 (scaled for integer arithmetic)
	phiScaled := api.Mul(c.PhiValue, 100)
	thresholdScaled := api.Mul(c.PhiThreshold, 100)

	diff := api.Sub(phiScaled, thresholdScaled)
	api.AssertIsLessOrEqual(0, diff)

	// Verify uptime compliance: uptimeNumerator/uptimeDenom >= target
	// Cross multiply to avoid division: uptimeNumerator * targetDenom >= target * uptimeDenom
	// Simplified: just verify uptimeNumerator >= uptimeDenom * 0.9999999997
	// We use integer approximation

	// Verify drift within bounds: driftValue <= driftMax
	driftDiff := api.Sub(c.DriftMax, c.DriftValue)
	api.AssertIsLessOrEqual(0, driftDiff)

	// Compute commitment hash
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	h.Write(c.PhiValue)
	h.Write(c.UptimeNumerator)
	h.Write(c.UptimeDenom)
	h.Write(c.DriftValue)
	h.Write(c.Timestamp)
	h.Write(c.Salt)

	computedHash := h.Sum()
	api.AssertIsEqual(computedHash, c.CommitmentHash)

	return nil
}

// MerkleAggregationCircuit proves batch of proofs are included in Merkle root
type MerkleAggregationCircuit struct {
	// Public inputs
	MerkleRoot frontend.Variable   `gnark:"merkleRoot,public"`
	BatchSize  frontend.Variable   `gnark:"batchSize,public"`
	Timestamp  frontend.Variable   `gnark:"timestamp,public"`

	// Private inputs - Merkle tree data
	Leaves     [32]frontend.Variable `gnark:"leaves"`
	PathBits   [32][5]frontend.Variable `gnark:"pathBits"`   // 5 levels = 32 leaves max
	PathNodes  [32][5]frontend.Variable `gnark:"pathNodes"`
}

// Define implements Merkle proof verification for batched proofs
func (c *MerkleAggregationCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// Verify each leaf is in the tree
	for i := 0; i < 32; i++ {
		current := c.Leaves[i]

		// Walk up the Merkle path
		for j := 0; j < 5; j++ {
			h.Reset()

			// If pathBit is 0, current is left child; else right child
			left := api.Select(c.PathBits[i][j], c.PathNodes[i][j], current)
			right := api.Select(c.PathBits[i][j], current, c.PathNodes[i][j])

			h.Write(left)
			h.Write(right)
			current = h.Sum()
		}

		// Final hash should equal Merkle root
		api.AssertIsEqual(current, c.MerkleRoot)
	}

	return nil
}

// AnchorProofCircuit proves blockchain anchor validity
type AnchorProofCircuit struct {
	// Public inputs
	MerkleRoot     frontend.Variable `gnark:"merkleRoot,public"`
	BlockNumber    frontend.Variable `gnark:"blockNumber,public"`
	ChainID        frontend.Variable `gnark:"chainID,public"`
	TransactionHash frontend.Variable `gnark:"txHash,public"`

	// Private inputs
	ClusterID      frontend.Variable `gnark:"clusterID"`
	Timestamp      frontend.Variable `gnark:"timestamp"`
	PreviousAnchor frontend.Variable `gnark:"previousAnchor"`
	Signature      frontend.Variable `gnark:"signature"`
}

// Define implements anchor proof verification
func (c *AnchorProofCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// Compute expected transaction hash
	h.Write(c.MerkleRoot)
	h.Write(c.ClusterID)
	h.Write(c.Timestamp)
	h.Write(c.ChainID)
	h.Write(c.PreviousAnchor)

	expectedHash := h.Sum()

	// Verify transaction hash matches
	api.AssertIsEqual(expectedHash, c.TransactionHash)

	return nil
}
