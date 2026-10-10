use anchor_lang::prelude::*;
use anchor_lang::solana_program::keccak;

declare_id!("DD7Anchor111111111111111111111111111111111");

/// DD7 Sovereign Anchor Program for Solana
/// Provides immutable blockchain anchoring for attestation proofs
#[program]
pub mod dd7_anchor {
    use super::*;

    /// Initialize a new cluster for anchoring
    pub fn initialize_cluster(
        ctx: Context<InitializeCluster>,
        cluster_id: [u8; 32],
        min_anchor_interval: i64,
    ) -> Result<()> {
        let cluster = &mut ctx.accounts.cluster;
        cluster.cluster_id = cluster_id;
        cluster.authority = ctx.accounts.authority.key();
        cluster.anchor_count = 0;
        cluster.latest_anchor = [0u8; 32];
        cluster.min_anchor_interval = min_anchor_interval;
        cluster.last_anchor_time = 0;
        cluster.active = true;
        cluster.bump = ctx.bumps.cluster;

        emit!(ClusterInitialized {
            cluster_id,
            authority: cluster.authority,
            min_anchor_interval,
        });

        Ok(())
    }

    /// Submit a new anchor record
    pub fn anchor(
        ctx: Context<SubmitAnchor>,
        merkle_root: [u8; 32],
        batch_size: u64,
        proof_commitment: [u8; 32],
    ) -> Result<()> {
        let cluster = &mut ctx.accounts.cluster;
        let anchor_record = &mut ctx.accounts.anchor_record;
        let clock = Clock::get()?;

        // Validate cluster is active
        require!(cluster.active, DD7Error::ClusterNotActive);

        // Validate anchor interval
        require!(
            clock.unix_timestamp >= cluster.last_anchor_time + cluster.min_anchor_interval,
            DD7Error::AnchorIntervalNotMet
        );

        // Compute anchor hash
        let anchor_hash = compute_anchor_hash(
            &merkle_root,
            &cluster.cluster_id,
            &cluster.latest_anchor,
            clock.unix_timestamp as u64,
            clock.slot,
            batch_size,
            &proof_commitment,
        );

        // Store anchor record
        anchor_record.anchor_hash = anchor_hash;
        anchor_record.merkle_root = merkle_root;
        anchor_record.cluster_id = cluster.cluster_id;
        anchor_record.previous_anchor = cluster.latest_anchor;
        anchor_record.timestamp = clock.unix_timestamp;
        anchor_record.slot = clock.slot;
        anchor_record.batch_size = batch_size;
        anchor_record.proof_commitment = proof_commitment;
        anchor_record.submitter = ctx.accounts.submitter.key();
        anchor_record.bump = ctx.bumps.anchor_record;

        // Update cluster state
        cluster.latest_anchor = anchor_hash;
        cluster.anchor_count += 1;
        cluster.last_anchor_time = clock.unix_timestamp;

        emit!(AnchorCreated {
            anchor_hash,
            cluster_id: cluster.cluster_id,
            merkle_root,
            timestamp: clock.unix_timestamp,
            batch_size,
        });

        Ok(())
    }

    /// Verify a Merkle proof against an anchored root
    pub fn verify_merkle_proof(
        ctx: Context<VerifyProof>,
        leaf: [u8; 32],
        proof: Vec<[u8; 32]>,
        index: u64,
    ) -> Result<bool> {
        let anchor_record = &ctx.accounts.anchor_record;

        let mut computed_hash = leaf;
        let mut idx = index;

        for sibling in proof.iter() {
            if idx % 2 == 0 {
                computed_hash = keccak::hashv(&[&computed_hash, sibling]).0;
            } else {
                computed_hash = keccak::hashv(&[sibling, &computed_hash]).0;
            }
            idx /= 2;
        }

        let valid = computed_hash == anchor_record.merkle_root;

        emit!(ProofVerified {
            anchor_hash: anchor_record.anchor_hash,
            valid,
        });

        Ok(valid)
    }

    /// Deactivate a cluster (admin only)
    pub fn deactivate_cluster(ctx: Context<DeactivateCluster>) -> Result<()> {
        let cluster = &mut ctx.accounts.cluster;
        cluster.active = false;

        emit!(ClusterDeactivated {
            cluster_id: cluster.cluster_id,
        });

        Ok(())
    }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

fn compute_anchor_hash(
    merkle_root: &[u8; 32],
    cluster_id: &[u8; 32],
    previous_anchor: &[u8; 32],
    timestamp: u64,
    slot: u64,
    batch_size: u64,
    proof_commitment: &[u8; 32],
) -> [u8; 32] {
    keccak::hashv(&[
        merkle_root,
        cluster_id,
        previous_anchor,
        &timestamp.to_le_bytes(),
        &slot.to_le_bytes(),
        &batch_size.to_le_bytes(),
        proof_commitment,
    ])
    .0
}

// =============================================================================
// ACCOUNTS
// =============================================================================

#[derive(Accounts)]
#[instruction(cluster_id: [u8; 32])]
pub struct InitializeCluster<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + ClusterAccount::SIZE,
        seeds = [b"cluster", cluster_id.as_ref()],
        bump
    )]
    pub cluster: Account<'info, ClusterAccount>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SubmitAnchor<'info> {
    #[account(
        mut,
        seeds = [b"cluster", cluster.cluster_id.as_ref()],
        bump = cluster.bump
    )]
    pub cluster: Account<'info, ClusterAccount>,

    #[account(
        init,
        payer = submitter,
        space = 8 + AnchorRecord::SIZE,
        seeds = [
            b"anchor",
            cluster.cluster_id.as_ref(),
            &cluster.anchor_count.to_le_bytes()
        ],
        bump
    )]
    pub anchor_record: Account<'info, AnchorRecord>,

    #[account(mut)]
    pub submitter: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct VerifyProof<'info> {
    pub anchor_record: Account<'info, AnchorRecord>,
}

#[derive(Accounts)]
pub struct DeactivateCluster<'info> {
    #[account(
        mut,
        seeds = [b"cluster", cluster.cluster_id.as_ref()],
        bump = cluster.bump,
        has_one = authority
    )]
    pub cluster: Account<'info, ClusterAccount>,

    pub authority: Signer<'info>,
}

// =============================================================================
// STATE
// =============================================================================

#[account]
pub struct ClusterAccount {
    pub cluster_id: [u8; 32],
    pub authority: Pubkey,
    pub anchor_count: u64,
    pub latest_anchor: [u8; 32],
    pub min_anchor_interval: i64,
    pub last_anchor_time: i64,
    pub active: bool,
    pub bump: u8,
}

impl ClusterAccount {
    pub const SIZE: usize = 32 + 32 + 8 + 32 + 8 + 8 + 1 + 1;
}

#[account]
pub struct AnchorRecord {
    pub anchor_hash: [u8; 32],
    pub merkle_root: [u8; 32],
    pub cluster_id: [u8; 32],
    pub previous_anchor: [u8; 32],
    pub timestamp: i64,
    pub slot: u64,
    pub batch_size: u64,
    pub proof_commitment: [u8; 32],
    pub submitter: Pubkey,
    pub bump: u8,
}

impl AnchorRecord {
    pub const SIZE: usize = 32 + 32 + 32 + 32 + 8 + 8 + 8 + 32 + 32 + 1;
}

// =============================================================================
// EVENTS
// =============================================================================

#[event]
pub struct ClusterInitialized {
    pub cluster_id: [u8; 32],
    pub authority: Pubkey,
    pub min_anchor_interval: i64,
}

#[event]
pub struct AnchorCreated {
    pub anchor_hash: [u8; 32],
    pub cluster_id: [u8; 32],
    pub merkle_root: [u8; 32],
    pub timestamp: i64,
    pub batch_size: u64,
}

#[event]
pub struct ClusterDeactivated {
    pub cluster_id: [u8; 32],
}

#[event]
pub struct ProofVerified {
    pub anchor_hash: [u8; 32],
    pub valid: bool,
}

// =============================================================================
// ERRORS
// =============================================================================

#[error_code]
pub enum DD7Error {
    #[msg("Cluster is not active")]
    ClusterNotActive,

    #[msg("Anchor interval not met")]
    AnchorIntervalNotMet,

    #[msg("Invalid Merkle proof")]
    InvalidMerkleProof,

    #[msg("Unauthorized")]
    Unauthorized,
}
