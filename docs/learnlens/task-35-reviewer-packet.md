# Task 35 blinded independent assessment packet

DRAFT / synthetic content. Expert names and decisions remain blank.
Do not consult the draft expected answers or system outputs during independent rating.
These are criterion probes, not complete approved multipart course assessments.
Supported stages allow unrestricted approved conceptual hints. Unaided transfer has no conceptual help; permitted accessibility support remains available in both stages.
Provide two separate copies to independently trained reviewers. Keep the author bundle and variant labels hidden until both ratings are locked. IDs are opaque and order is shuffled.

## Source register

- [H23](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.HGate): Qiskit SDK 2.3 API documentation (pinned; not asserted latest); Matrix representation; inverse. Accessed 2026-09-10; case approval pending.
- [X23](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.XGate): Qiskit SDK 2.3 API documentation (pinned; not asserted latest); Matrix representation; inverse. Accessed 2026-09-10; case approval pending.
- [CX23](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.CXGate): Qiskit SDK 2.3 API documentation (pinned; not asserted latest); Matrix representation; little-endian convention. Accessed 2026-09-10; case approval pending.
- [STATE23](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.quantum_info.Statevector): Qiskit SDK 2.3 API documentation (pinned; not asserted latest); from_instruction; probabilities; sample_counts. Accessed 2026-09-10; case approval pending.
- [BITS](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering): unversioned guide; Integers; Strings; Statevector matrices. Accessed 2026-09-10; case approval pending.
- [POLICY](task-08-approved-selections.md): task-08-selections-v1; D-04, D-05, D-07. Accessed 2026-09-10; case approval pending.

## T35-095

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

Only the control-one subspace is exchanged by CX; this basis vector remains 10, so B.

Reviewer decision: ______  Reason/evidence: ______

## T35-086

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

CX maps the two input branches to 00 and 11; P(01)=0 differs from the product of marginals, 1/4.

Reviewer decision: ______  Reason/evidence: ______

## T35-018

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

Response in a text field:
- The second column of H has amplitudes +1/sqrt(2), -1/sqrt(2); squared magnitudes are equal.

Reviewer decision: ______  Reason/evidence: ______

## T35-034

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

I first identify the initial state and follow the stated gate order. C: P(1)=1 because X exchanges the basis states. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-015

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

(|0>-|1>)/sqrt(2); each squared amplitude is 1/2.

Reviewer decision: ______  Reason/evidence: ______

## T35-016

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

I first identify the initial state and follow the stated gate order. The state is (|0>-|1>)/sqrt(2). Each computational outcome has probability 1/2. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-055

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

The final state is |0>: H makes |+>, X preserves it, and H maps it to |0>.

Reviewer decision: ______  Reason/evidence: ______

## T35-057

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

It cancels somehow.

Reviewer decision: ______  Reason/evidence: ______

## T35-009

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

Response in a text field:
- The two amplitudes have equal squared modulus, 1/2; shot counts fluctuate.

Reviewer decision: ______  Reason/evidence: ______

## T35-014

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

The second column of H has amplitudes +1/sqrt(2), -1/sqrt(2); squared magnitudes are equal.

Reviewer decision: ______  Reason/evidence: ______

## T35-058

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

The result is zero; no intermediate-state explanation is supplied.

Reviewer decision: ______  Reason/evidence: ______

## T35-076

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

10, without explaining the mapping.

Reviewer decision: ______  Reason/evidence: ______

## T35-065

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

10; q0 must be the leftmost character because it is drawn at the top.

Reviewer decision: ______  Reason/evidence: ______

## T35-027

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: structured_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

Response in a text field:
- Multiplying H by H cancels the |1> amplitude and restores |0>.

Reviewer decision: ______  Reason/evidence: ______

## T35-012

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

It is the opposite superposition.

Reviewer decision: ______  Reason/evidence: ______

## T35-051

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

A,C. X swaps equal amplitudes, leaving |+>.

Reviewer decision: ______  Reason/evidence: ______

## T35-023

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

Multiplying H by H cancels the |1> amplitude and restores |0>.

Reviewer decision: ______  Reason/evidence: ______

## T35-063

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: structured_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

Response in a text field:
- HXH is Z, and Z leaves initial |0> unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-102

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

Everything is possible.

Reviewer decision: ______  Reason/evidence: ______

## T35-082

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

The state is (|00>+|11>)/sqrt(2). Each bit is balanced, but only matching pairs occur.

Reviewer decision: ______  Reason/evidence: ______

## T35-046

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

A and C. X exchanges two equal amplitudes and leaves |+> unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-098

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

Dictated response: Only the control-one subspace is exchanged by CX; this basis vector remains 10, so B.

Reviewer decision: ______  Reason/evidence: ______

## T35-083

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

Each qubit is 50/50, so all four joint strings are equally likely.

Reviewer decision: ______  Reason/evidence: ______

## T35-006

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

P(0)=P(1)=1/2; finite counts fluctuate.

Reviewer decision: ______  Reason/evidence: ______

## T35-041

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Use x since the Pauli-X matrix is its own inverse.

Reviewer decision: ______  Reason/evidence: ______

## T35-101

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

B: any two superposed qubits are entangled.

Reviewer decision: ______  Reason/evidence: ______

## T35-028

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

C: P(1)=1 because X exchanges the basis states.

Reviewer decision: ______  Reason/evidence: ______

## T35-045

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: structured_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Response in a text field:
- Use x since the Pauli-X matrix is its own inverse.

Reviewer decision: ______  Reason/evidence: ______

## T35-024

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

P(0)=1: H H = I without intervening measurement.

Reviewer decision: ______  Reason/evidence: ______

## T35-019

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

Zero occurs with probability one because H squared is the identity.

Reviewer decision: ______  Reason/evidence: ______

## T35-049

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

C, because the counts look balanced; the state statement is omitted.

Reviewer decision: ______  Reason/evidence: ______

## T35-052

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

I first identify the initial state and follow the stated gate order. A and C. X exchanges two equal amplitudes and leaves |+> unchanged. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-001

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

P(0)=P(1)=1/2; finite counts need not split exactly equally.

Reviewer decision: ______  Reason/evidence: ______

## T35-067

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

01, with no explanation of the convention.

Reviewer decision: ______  Reason/evidence: ______

## T35-060

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

|0> -> |+> -> |+> -> |0>.

Reviewer decision: ______  Reason/evidence: ______

## T35-085

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

Only 00 and 11 occur; the coherent state and independence distinction are missing.

Reviewer decision: ______  Reason/evidence: ______

## T35-100

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

A and C. Independent H gates make |+> tensor |+>, with equal probabilities for all four strings.

Reviewer decision: ______  Reason/evidence: ______

## T35-054

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

Response in a text field:
- A,C: |+> is the +1 eigenvector of X, so the state is unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-005

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

The two amplitudes have equal squared modulus, 1/2; shot counts fluctuate.

Reviewer decision: ______  Reason/evidence: ______

## T35-079

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

I first identify the initial state and follow the stated gate order. 10; q1 contributes the leftmost bit in this two-bit register. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-077

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

The classical value is 2^1=2, written as 10 in binary.

Reviewer decision: ______  Reason/evidence: ______

## T35-070

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

I first identify the initial state and follow the stated gate order. 01; q0 is the rightmost bit in the displayed string. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-072

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

Response in a text field:
- The displayed integer is 2^0=1, padded to two binary digits: 01.

Reviewer decision: ______  Reason/evidence: ______

## T35-107

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

Dictated response: A,C: the four amplitudes factor as (1,1)/square root of two tensor (1,1)/square root of two.

Reviewer decision: ______  Reason/evidence: ______

## T35-106

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

I first identify the initial state and follow the stated gate order. A and C. Independent H gates make |+> tensor |+>, with equal probabilities for all four strings. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-059

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

HXH is Z, and Z leaves initial |0> unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-094

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

B, but the control condition is unexplained.

Reviewer decision: ______  Reason/evidence: ______

## T35-099

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

Response in a text field:
- Only the control-one subspace is exchanged by CX; this basis vector remains 10, so B.

Reviewer decision: ______  Reason/evidence: ______

## T35-030

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

The last one, probably.

Reviewer decision: ______  Reason/evidence: ______

## T35-039

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Undo it.

Reviewer decision: ______  Reason/evidence: ______

## T35-050

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

A,C: |+> is the +1 eigenvector of X, so the state is unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-080

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: dictated_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

Dictated response: The classical value is 2^1=2, written as 10 in binary.

Reviewer decision: ______  Reason/evidence: ______

## T35-078

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

10: q1 is the leftmost bit in q1q0 order.

Reviewer decision: ______  Reason/evidence: ______

## T35-025

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

I first identify the initial state and follow the stated gate order. Zero occurs with probability one because H squared is the identity. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-040

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Use x, but no explanation is supplied.

Reviewer decision: ______  Reason/evidence: ______

## T35-026

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: dictated_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

Dictated response: Multiplying H by H cancels the ket one amplitude and restores ket zero.

Reviewer decision: ______  Reason/evidence: ______

## T35-087

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

(|00>+|11>)/sqrt(2): balanced marginals, only matching pairs.

Reviewer decision: ______  Reason/evidence: ______

## T35-032

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

X times the column vector (1,0) gives (0,1), so C.

Reviewer decision: ______  Reason/evidence: ______

## T35-061

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

I first identify the initial state and follow the stated gate order. The final state is |0>: H makes |+>, X preserves it, and H maps it to |0>. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-029

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

B: every quantum gate produces a fair random outcome.

Reviewer decision: ______  Reason/evidence: ______

## T35-053

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

Dictated response: A,C: |+> is the +1 eigenvector of X, so the state is unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-069

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

01: q0 is the least significant, rightmost bit.

Reviewer decision: ______  Reason/evidence: ______

## T35-035

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

Dictated response: X times the column vector (1,0) gives (0,1), so C.

Reviewer decision: ______  Reason/evidence: ______

## T35-105

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

A,C: |+> tensor |+> gives four squared amplitudes of 1/4.

Reviewer decision: ______  Reason/evidence: ______

## T35-108

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

Response in a text field:
- A,C: the four amplitudes factor as (1,1)/sqrt(2) tensor (1,1)/sqrt(2).

Reviewer decision: ______  Reason/evidence: ______

## T35-074

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

01; all flipped qubits are printed on the right.

Reviewer decision: ______  Reason/evidence: ______

## T35-038

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Use h. H always resets any qubit to zero.

Reviewer decision: ______  Reason/evidence: ______

## T35-091

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

B: 10. The zero control q0 does not flip target q1.

Reviewer decision: ______  Reason/evidence: ______

## T35-089

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

Dictated response: CX maps the two input branches to 00 and 11; P(01)=0 differs from the product of marginals, 1/4.

Reviewer decision: ______  Reason/evidence: ______

## T35-062

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: dictated_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

Dictated response: HXH is Z, and Z leaves initial ket zero unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-010

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

The state is (|0>-|1>)/sqrt(2). Each computational outcome has probability 1/2.

Reviewer decision: ______  Reason/evidence: ______

## T35-022

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

The result is zero, but I cannot justify the cancellation.

Reviewer decision: ______  Reason/evidence: ______

## T35-081

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: structured_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

Response in a text field:
- The classical value is 2^1=2, written as 10 in binary.

Reviewer decision: ______  Reason/evidence: ______

## T35-021

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

It goes back.

Reviewer decision: ______  Reason/evidence: ______

## T35-011

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

The minus sign makes the probability of one negative.

Reviewer decision: ______  Reason/evidence: ______

## T35-042

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

x: X X = I, so |0> returns.

Reviewer decision: ______  Reason/evidence: ______

## T35-031

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

C, without a justification.

Reviewer decision: ______  Reason/evidence: ______

## T35-003

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

It is half.

Reviewer decision: ______  Reason/evidence: ______

## T35-007

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

I first identify the initial state and follow the stated gate order. P(0)=P(1)=1/2; finite counts need not split exactly equally. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-093

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

No change, I think.

Reviewer decision: ______  Reason/evidence: ______

## T35-103

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

A; I have not explained whether the state factors.

Reviewer decision: ______  Reason/evidence: ______

## T35-004

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

Both outcomes can occur, but I cannot specify their probabilities.

Reviewer decision: ______  Reason/evidence: ______

## T35-048

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

The equal ones.

Reviewer decision: ______  Reason/evidence: ______

## T35-064

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

01; q0 is the rightmost bit in the displayed string.

Reviewer decision: ______  Reason/evidence: ______

## T35-090

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

Response in a text field:
- CX maps the two input branches to 00 and 11; P(01)=0 differs from the product of marginals, 1/4.

Reviewer decision: ______  Reason/evidence: ______

## T35-088

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

I first identify the initial state and follow the stated gate order. The state is (|00>+|11>)/sqrt(2). Each bit is balanced, but only matching pairs occur. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-066

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

One zero and one one.

Reviewer decision: ______  Reason/evidence: ______

## T35-002

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

H guarantees exactly half zero and half one in every finite run.

Reviewer decision: ______  Reason/evidence: ______

## T35-092

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

A: 00. CX always flips its target regardless of the control.

Reviewer decision: ______  Reason/evidence: ______

## T35-013

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

Both outcomes have probability 1/2; I have not identified the relative phase.

Reviewer decision: ______  Reason/evidence: ______

## T35-075

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

The other order.

Reviewer decision: ______  Reason/evidence: ______

## T35-047

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

For |0> followed by H then X, select all true statements and justify: A the final state is |+>; B P(1)=1; C both probabilities are 1/2.

Response:

B only: the last X forces every input state to |1>.

Reviewer decision: ______  Reason/evidence: ______

## T35-084

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply H on q0 then CX with control q0 and target q1. Explain the state and why equal individual marginals do not mean independent outcomes.

Response:

They are linked.

Reviewer decision: ______  Reason/evidence: ______

## T35-036

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: structured_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

Response in a text field:
- X times the column vector (1,0) gives (0,1), so C.

Reviewer decision: ______  Reason/evidence: ______

## T35-068

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

The displayed integer is 2^0=1, padded to two binary digits: 01.

Reviewer decision: ______  Reason/evidence: ______

## T35-104

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: STATE23, BITS, POLICY

For |00> followed by H on each qubit, select and justify: A all four strings have probability 1/4; B the state is necessarily entangled; C it is a product of |+> states.

Response:

A,C: the four amplitudes factor as (1,1)/sqrt(2) tensor (1,1)/sqrt(2).

Reviewer decision: ______  Reason/evidence: ______

## T35-008

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Starting in |0>, apply H then measure in the computational basis. Predict probabilities and distinguish them from finite-shot counts.

Response:

Dictated response: The two amplitudes have equal squared modulus, 1/2; shot counts fluctuate.

Reviewer decision: ______  Reason/evidence: ______

## T35-073

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Fresh unaided exercise: two zero qubits, X on q1, identity measurement mapping. State the Qiskit output and justify.

Response:

10; q1 contributes the leftmost bit in this two-bit register.

Reviewer decision: ______  Reason/evidence: ______

## T35-033

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Select and justify: X acts on |0>. Is P(1) A: 0, B: 1/2, or C: 1? A selection alone does not supply the required justification.

Response:

C. X|0>=|1>.

Reviewer decision: ______  Reason/evidence: ______

## T35-056

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: predict |0> after H, X, H without intermediate measurements. Explain the sequence.

Response:

The middle X guarantees a final one regardless of the last H.

Reviewer decision: ______  Reason/evidence: ______

## T35-037

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Use x. The second X flips |1> back to |0>.

Reviewer decision: ______  Reason/evidence: ______

## T35-020

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

Fresh unaided exercise: |0> enters two consecutive H gates with no intermediate measurement. Predict the final measurement and explain why.

Response:

Two Hadamards give two independent coin flips so the final outcome is 50/50.

Reviewer decision: ______  Reason/evidence: ______

## T35-044

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: dictated_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

Dictated response: Use x since the Pauli-X matrix is its own inverse.

Reviewer decision: ______  Reason/evidence: ______

## T35-096

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

B: 10. q0=0, so CX leaves q1 unchanged.

Reviewer decision: ______  Reason/evidence: ______

## T35-017

Criterion: Q-EXPL-v1: Draft explanation probe: explain the requested state/relationship, including required distinctions.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: H23, STATE23, BITS, POLICY

From |0>, run x(0); h(0). Explain the final state, including the relative sign and computational-basis probabilities.

Response:

Dictated response: The second column of H has amplitudes +1/square root of two, -1/square root of two; squared magnitudes are equal.

Reviewer decision: ______  Reason/evidence: ______

## T35-097

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: typed_text (equivalence pending).
Source IDs: CX23, STATE23, BITS, POLICY

From |00>, apply X to q1 then CX(q0,q1). Select and justify the final string: A 00, B 10, C 11, using q1q0 order.

Response:

I first identify the initial state and follow the stated gate order. B: 10. The zero control q0 does not flip target q1. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-043

Criterion: Q-APPLY-v1: Draft fresh application probe: apply the principle to this separate unaided form and justify it.
Stage: unaided_transfer; access form: typed_text (equivalence pending).
Source IDs: X23, STATE23, BITS, POLICY

Fresh unaided exercise: complete qc.x(0); qc.____(0) using X to return initial |0> to |0>. Explain the completed code.

Response:

I first identify the initial state and follow the stated gate order. Use x. The second X flips |1> back to |0>. This prediction concerns the ideal circuit and the specified measurement, not an experimental noise model.

Reviewer decision: ______  Reason/evidence: ______

## T35-071

Criterion: Q-PRED-v1: Draft prediction probe: correct ideal probabilities/output and the requested justification.
Stage: supported; access form: dictated_text (equivalence pending).
Source IDs: BITS, STATE23, POLICY

Two qubits start at zero. Run x(0), measure q[i] to c[i]. Predict Qiskit's two-character output string and explain its order.

Response:

Dictated response: The displayed integer is 2^0=1, padded to two binary digits: 01.

Reviewer decision: ______  Reason/evidence: ______
