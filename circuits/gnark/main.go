// DD7 Zero-Knowledge Proof System
// Sovereign-grade proving and verification for attestation, compliance, and anchoring
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

var (
	mode        = flag.String("mode", "setup", "Mode: setup, prove, verify")
	circuit     = flag.String("circuit", "attestation", "Circuit: attestation, phi, merkle, anchor")
	pkPath      = flag.String("pk", "proving.key", "Proving key path")
	vkPath      = flag.String("vk", "verifying.key", "Verifying key path")
	witnessPath = flag.String("witness", "witness.json", "Witness JSON path")
	proofPath   = flag.String("proof", "proof.bin", "Proof output path")
	publicPath  = flag.String("public", "public.json", "Public inputs JSON path")
)

func main() {
	flag.Parse()

	switch *mode {
	case "setup":
		runSetup(*circuit, *pkPath, *vkPath)
	case "prove":
		runProve(*circuit, *pkPath, *witnessPath, *proofPath, *publicPath)
	case "verify":
		runVerify(*circuit, *vkPath, *proofPath, *publicPath)
	default:
		fmt.Fprintf(os.Stderr, "Unknown mode: %s\n", *mode)
		os.Exit(1)
	}
}

func runSetup(circuitName, pkPath, vkPath string) {
	fmt.Printf("Setting up %s circuit...\n", circuitName)

	var circuit frontend.Circuit
	switch circuitName {
	case "attestation":
		circuit = &AttestationCircuit{}
	case "phi":
		circuit = &PhiComplianceCircuit{}
	case "merkle":
		circuit = &MerkleAggregationCircuit{}
	case "anchor":
		circuit = &AnchorProofCircuit{}
	default:
		fmt.Fprintf(os.Stderr, "Unknown circuit: %s\n", circuitName)
		os.Exit(1)
	}

	// Compile circuit
	cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, circuit)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to compile circuit: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Circuit compiled: %d constraints\n", cs.GetNbConstraints())

	// Generate proving and verifying keys
	pk, vk, err := groth16.Setup(cs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to setup: %v\n", err)
		os.Exit(1)
	}

	// Save proving key
	pkFile, err := os.Create(pkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create proving key file: %v\n", err)
		os.Exit(1)
	}
	defer pkFile.Close()

	_, err = pk.WriteTo(pkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write proving key: %v\n", err)
		os.Exit(1)
	}

	// Save verifying key
	vkFile, err := os.Create(vkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create verifying key file: %v\n", err)
		os.Exit(1)
	}
	defer vkFile.Close()

	_, err = vk.WriteTo(vkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write verifying key: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Setup complete. Keys saved to %s and %s\n", pkPath, vkPath)
}

func runProve(circuitName, pkPath, witnessPath, proofPath, publicPath string) {
	fmt.Printf("Generating proof for %s circuit...\n", circuitName)

	// Load proving key
	pkFile, err := os.Open(pkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open proving key: %v\n", err)
		os.Exit(1)
	}
	defer pkFile.Close()

	pk := groth16.NewProvingKey(ecc.BN254)
	_, err = pk.ReadFrom(pkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read proving key: %v\n", err)
		os.Exit(1)
	}

	// Load witness
	witnessFile, err := os.ReadFile(witnessPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read witness: %v\n", err)
		os.Exit(1)
	}

	var witnessData map[string]interface{}
	err = json.Unmarshal(witnessFile, &witnessData)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to parse witness JSON: %v\n", err)
		os.Exit(1)
	}

	// Create circuit with witness
	var circuit frontend.Circuit
	switch circuitName {
	case "attestation":
		circuit = &AttestationCircuit{}
	case "phi":
		circuit = &PhiComplianceCircuit{}
	case "merkle":
		circuit = &MerkleAggregationCircuit{}
	case "anchor":
		circuit = &AnchorProofCircuit{}
	}

	// Compile and create witness
	cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, circuit)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to compile: %v\n", err)
		os.Exit(1)
	}

	witness, err := frontend.NewWitness(circuit, ecc.BN254.ScalarField())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create witness: %v\n", err)
		os.Exit(1)
	}

	// Generate proof
	proof, err := groth16.Prove(cs, pk, witness)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to generate proof: %v\n", err)
		os.Exit(1)
	}

	// Save proof
	proofFile, err := os.Create(proofPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create proof file: %v\n", err)
		os.Exit(1)
	}
	defer proofFile.Close()

	_, err = proof.WriteTo(proofFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write proof: %v\n", err)
		os.Exit(1)
	}

	// Extract and save public inputs
	publicWitness, err := witness.Public()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to extract public inputs: %v\n", err)
		os.Exit(1)
	}

	publicFile, err := os.Create(publicPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create public inputs file: %v\n", err)
		os.Exit(1)
	}
	defer publicFile.Close()

	publicJSON, _ := json.MarshalIndent(publicWitness, "", "  ")
	publicFile.Write(publicJSON)

	fmt.Printf("Proof generated and saved to %s\n", proofPath)
}

func runVerify(circuitName, vkPath, proofPath, publicPath string) {
	fmt.Printf("Verifying proof for %s circuit...\n", circuitName)

	// Load verifying key
	vkFile, err := os.Open(vkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open verifying key: %v\n", err)
		os.Exit(1)
	}
	defer vkFile.Close()

	vk := groth16.NewVerifyingKey(ecc.BN254)
	_, err = vk.ReadFrom(vkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read verifying key: %v\n", err)
		os.Exit(1)
	}

	// Load proof
	proofFile, err := os.Open(proofPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open proof: %v\n", err)
		os.Exit(1)
	}
	defer proofFile.Close()

	proof := groth16.NewProof(ecc.BN254)
	_, err = proof.ReadFrom(proofFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read proof: %v\n", err)
		os.Exit(1)
	}

	// Create public witness
	var circuit frontend.Circuit
	switch circuitName {
	case "attestation":
		circuit = &AttestationCircuit{}
	case "phi":
		circuit = &PhiComplianceCircuit{}
	case "merkle":
		circuit = &MerkleAggregationCircuit{}
	case "anchor":
		circuit = &AnchorProofCircuit{}
	}

	publicWitness, err := frontend.NewWitness(circuit, ecc.BN254.ScalarField(), frontend.PublicOnly())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create public witness: %v\n", err)
		os.Exit(1)
	}

	// Verify
	err = groth16.Verify(proof, vk, publicWitness)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Verification FAILED: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("✓ Proof verified successfully")
}
