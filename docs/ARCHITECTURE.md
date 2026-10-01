# Maintained boundaries

- `recovery_capacity.py`: inverse action cost and capacity remaining after a proposal.
- `transaction_state.py`: execution, active obligation, restoration and commit records.
- `commit_ledger.py`: public state-effect accounting and no-effect quarantine.
- `pact_controller*`: transaction admission, restoration and fail-closed control.
- `typed_observation*`, `typed_contracts*`, `pact_grounding*`: observable-state contracts and evidence/certificates.
- `webarena_*`, `confirmation_agents*`: browser/environment adapters.
- `confirmation_statistics_v7`, `inversereserve_final_v1` and successor design modules: frozen statistical definitions and analysis.

The package remains `rcrps` for compatibility. Existing versioned names export
the extracted state/ledger/capacity logic. Predecessor modules that are actually
imported by final or successor drivers remain dependencies. A version suffix
does not make a module disposable; manuscript/remote launcher history is kept
outside the active package. The scientific final-v1 analysis and later scoped
capacity studies must not be relabeled as one experiment.
