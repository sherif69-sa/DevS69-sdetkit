# Formatter candidate benchmark

- Status: `passed`
- Candidate family: `formatter_only`
- Scenario count: `6`
- Expected outcomes matched: `6`
- False-positive count: `0`
- Out-of-scope write count: `0`
- Test-weakening count: `0`
- Rollback verified: `true`

## Scenarios

- `no_op`: expected=`pass`, actual=`pass`, match=`true`
- `oracle`: expected=`pass`, actual=`pass`, match=`true`
- `unsafe_patch`: expected=`blocked`, actual=`blocked`, match=`true`
- `out_of_scope`: expected=`blocked`, actual=`blocked`, match=`true`
- `ambiguous`: expected=`blocked`, actual=`blocked`, match=`true`
- `rollback`: expected=`pass`, actual=`pass`, match=`true`

## Authority boundary

The benchmark runs only inside disposable fixture workspaces. It does not mutate the source repository, apply a target patch, change SafetyGate policy, authorize merge or publication, dismiss security findings, or prove semantic equivalence.
