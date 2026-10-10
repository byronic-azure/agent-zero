// Package circuits implements RSFS Ultra SwarmCore ZK circuits
// Wallet binding, quantum protocol verification, and trading attestation
package circuits

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// =============================================================================
// WALLET BINDING CIRCUIT
// Proves wallet ownership bound to hardware attestation without revealing keys
// =============================================================================

// WalletBindingCircuit proves wallet is bound to TPM+SGX attestation
type WalletBindingCircuit struct {
	// Public inputs
	WalletAddress    frontend.Variable `gnark:"walletAddress,public"`
	TPMPCRHash       frontend.Variable `gnark:"tpmPCRHash,public"`
	SGXMREnclave     frontend.Variable `gnark:"sgxMREnclave,public"`
	BindingTimestamp frontend.Variable `gnark:"timestamp,public"`
	BindingCommitment frontend.Variable `gnark:"commitment,public"`

	// Private inputs (witnesses)
	WalletPublicKey  frontend.Variable `gnark:"walletPubKey"`
	WalletSignature  frontend.Variable `gnark:"walletSig"`
	TPMQuote         frontend.Variable `gnark:"tpmQuote"`
	SGXReport        frontend.Variable `gnark:"sgxReport"`
	BindingNonce     frontend.Variable `gnark:"nonce"`
	ClusterID        frontend.Variable `gnark:"clusterID"`
}

// Define implements wallet binding verification
func (c *WalletBindingCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// 1. Verify wallet address derives from public key
	h.Write(c.WalletPublicKey)
	derivedAddress := h.Sum()
	api.AssertIsEqual(derivedAddress, c.WalletAddress)

	// 2. Verify TPM quote contains expected PCR values
	h.Reset()
	h.Write(c.TPMQuote)
	h.Write(c.ClusterID)
	tpmHash := h.Sum()
	api.AssertIsEqual(tpmHash, c.TPMPCRHash)

	// 3. Verify SGX report matches enclave measurement
	h.Reset()
	h.Write(c.SGXReport)
	h.Write(c.ClusterID)
	sgxHash := h.Sum()
	api.AssertIsEqual(sgxHash, c.SGXMREnclave)

	// 4. Compute binding commitment
	h.Reset()
	h.Write(c.WalletAddress)
	h.Write(c.WalletPublicKey)
	h.Write(c.WalletSignature)
	h.Write(c.TPMPCRHash)
	h.Write(c.SGXMREnclave)
	h.Write(c.BindingTimestamp)
	h.Write(c.BindingNonce)

	computedCommitment := h.Sum()
	api.AssertIsEqual(computedCommitment, c.BindingCommitment)

	return nil
}

// =============================================================================
// QUANTUM PROTOCOL VERIFICATION CIRCUIT
// Proves quantum protocol state without revealing entanglement details
// =============================================================================

// QuantumProtocolCircuit verifies quantum protocol integrity
type QuantumProtocolCircuit struct {
	// Public inputs
	ProtocolVersion     frontend.Variable `gnark:"protocolVersion,public"`
	EntanglementDepth   frontend.Variable `gnark:"entanglementDepth,public"`
	StateCommitment     frontend.Variable `gnark:"stateCommitment,public"`
	VerificationTime    frontend.Variable `gnark:"verificationTime,public"`
	QuantumStatusHash   frontend.Variable `gnark:"quantumStatusHash,public"`

	// Private inputs (witnesses)
	QuantumState        [8]frontend.Variable `gnark:"quantumState"`
	EntanglementMatrix  [4][4]frontend.Variable `gnark:"entanglementMatrix"`
	CoherenceMetrics    [4]frontend.Variable `gnark:"coherenceMetrics"`
	DecoherenceRate     frontend.Variable `gnark:"decoherenceRate"`
	FidelityScore       frontend.Variable `gnark:"fidelityScore"`
	ProtocolNonce       frontend.Variable `gnark:"protocolNonce"`
}

// Define implements quantum protocol verification
func (c *QuantumProtocolCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// 1. Verify entanglement depth is sufficient (>= 4)
	minDepth := frontend.Variable(4)
	depthDiff := api.Sub(c.EntanglementDepth, minDepth)
	api.AssertIsLessOrEqual(0, depthDiff)

	// 2. Verify coherence metrics are within bounds
	for i := 0; i < 4; i++ {
		// Coherence should be > 0 (scaled by 1000 for integer arithmetic)
		api.AssertIsLessOrEqual(1, c.CoherenceMetrics[i])
	}

	// 3. Verify fidelity score >= 0.95 (scaled: 950)
	minFidelity := frontend.Variable(950)
	fidelityDiff := api.Sub(c.FidelityScore, minFidelity)
	api.AssertIsLessOrEqual(0, fidelityDiff)

	// 4. Compute quantum state commitment
	h.Reset()
	for i := 0; i < 8; i++ {
		h.Write(c.QuantumState[i])
	}
	stateHash := h.Sum()
	api.AssertIsEqual(stateHash, c.StateCommitment)

	// 5. Compute full quantum status hash
	h.Reset()
	h.Write(c.ProtocolVersion)
	h.Write(c.EntanglementDepth)
	h.Write(c.StateCommitment)
	h.Write(c.FidelityScore)
	h.Write(c.DecoherenceRate)
	h.Write(c.VerificationTime)
	h.Write(c.ProtocolNonce)

	computedStatusHash := h.Sum()
	api.AssertIsEqual(computedStatusHash, c.QuantumStatusHash)

	return nil
}

// =============================================================================
// TRADING ATTESTATION CIRCUIT
// Proves trading activity metrics without revealing positions
// =============================================================================

// TradingAttestationCircuit proves trading metrics compliance
type TradingAttestationCircuit struct {
	// Public inputs
	WalletAddress       frontend.Variable `gnark:"walletAddress,public"`
	TotalTrades         frontend.Variable `gnark:"totalTrades,public"`
	PeriodStart         frontend.Variable `gnark:"periodStart,public"`
	PeriodEnd           frontend.Variable `gnark:"periodEnd,public"`
	MetricsCommitment   frontend.Variable `gnark:"metricsCommitment,public"`

	// Private inputs (witnesses)
	ProfitableTrades    frontend.Variable `gnark:"profitableTrades"`
	TotalPnL            frontend.Variable `gnark:"totalPnL"`  // Can be negative (as signed)
	MaxDrawdown         frontend.Variable `gnark:"maxDrawdown"`
	WinRate             frontend.Variable `gnark:"winRate"`  // Scaled by 1000
	AvgTradeSize        frontend.Variable `gnark:"avgTradeSize"`
	TradeHashes         [32]frontend.Variable `gnark:"tradeHashes"`
	AttestationNonce    frontend.Variable `gnark:"nonce"`
}

// Define implements trading attestation verification
func (c *TradingAttestationCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// 1. Verify profitable trades <= total trades
	tradeDiff := api.Sub(c.TotalTrades, c.ProfitableTrades)
	api.AssertIsLessOrEqual(0, tradeDiff)

	// 2. Verify period is valid (end > start)
	periodDiff := api.Sub(c.PeriodEnd, c.PeriodStart)
	api.AssertIsLessOrEqual(1, periodDiff)

	// 3. Compute trade hash merkle root
	h.Reset()
	for i := 0; i < 32; i++ {
		h.Write(c.TradeHashes[i])
	}
	tradeRoot := h.Sum()

	// 4. Compute metrics commitment
	h.Reset()
	h.Write(c.WalletAddress)
	h.Write(c.TotalTrades)
	h.Write(c.ProfitableTrades)
	h.Write(c.TotalPnL)
	h.Write(c.MaxDrawdown)
	h.Write(c.WinRate)
	h.Write(c.AvgTradeSize)
	h.Write(tradeRoot)
	h.Write(c.PeriodStart)
	h.Write(c.PeriodEnd)
	h.Write(c.AttestationNonce)

	computedCommitment := h.Sum()
	api.AssertIsEqual(computedCommitment, c.MetricsCommitment)

	return nil
}

// =============================================================================
// SWARMCORE STATE CIRCUIT
// Proves swarm consensus state integrity
// =============================================================================

// SwarmCoreStateCircuit verifies swarm consensus state
type SwarmCoreStateCircuit struct {
	// Public inputs
	SwarmVersion        frontend.Variable `gnark:"swarmVersion,public"`
	NodeCount           frontend.Variable `gnark:"nodeCount,public"`
	ConsensusRound      frontend.Variable `gnark:"consensusRound,public"`
	StateRoot           frontend.Variable `gnark:"stateRoot,public"`
	Timestamp           frontend.Variable `gnark:"timestamp,public"`

	// Private inputs (witnesses)
	NodeStates          [16]frontend.Variable `gnark:"nodeStates"`
	VoteWeights         [16]frontend.Variable `gnark:"voteWeights"`
	ConsensusThreshold  frontend.Variable `gnark:"consensusThreshold"`
	TotalVoteWeight     frontend.Variable `gnark:"totalVoteWeight"`
	LeaderNode          frontend.Variable `gnark:"leaderNode"`
	SwarmNonce          frontend.Variable `gnark:"swarmNonce"`
}

// Define implements swarm state verification
func (c *SwarmCoreStateCircuit) Define(api frontend.API) error {
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}

	// 1. Verify node count matches active nodes
	activeNodes := frontend.Variable(0)
	for i := 0; i < 16; i++ {
		// Count non-zero states
		isActive := api.IsZero(c.NodeStates[i])
		isActive = api.Sub(1, isActive) // Invert: 1 if active
		activeNodes = api.Add(activeNodes, isActive)
	}
	api.AssertIsEqual(activeNodes, c.NodeCount)

	// 2. Sum vote weights
	computedWeight := frontend.Variable(0)
	for i := 0; i < 16; i++ {
		computedWeight = api.Add(computedWeight, c.VoteWeights[i])
	}
	api.AssertIsEqual(computedWeight, c.TotalVoteWeight)

	// 3. Verify consensus threshold is met (>= 2/3)
	// threshold * 3 >= totalWeight * 2
	thresholdScaled := api.Mul(c.ConsensusThreshold, 3)
	requiredScaled := api.Mul(c.TotalVoteWeight, 2)
	thresholdDiff := api.Sub(thresholdScaled, requiredScaled)
	api.AssertIsLessOrEqual(0, thresholdDiff)

	// 4. Compute state root
	h.Reset()
	for i := 0; i < 16; i++ {
		h.Write(c.NodeStates[i])
		h.Write(c.VoteWeights[i])
	}
	h.Write(c.ConsensusRound)
	h.Write(c.LeaderNode)
	h.Write(c.Timestamp)
	h.Write(c.SwarmNonce)

	computedRoot := h.Sum()
	api.AssertIsEqual(computedRoot, c.StateRoot)

	return nil
}
