# Delivery-path objectives for black-box diffusion watermark forgery

Working methods and results sections. The complete three-method development screen closes the fixed delivery-path candidate: it passes ordinary Gaussian Shading on 6/12 tasks, compared with 8/12 for native Imprint, despite lower pixel distortion. These results do not establish a novel or superior attack method.

## Problem and evaluation boundary

We study whether a proxy-model optimization objective can transfer watermark evidence from a reference image to an image with a specified cover content. The attacker receives a watermarked reference image, a cover image, and the fixed proxy configuration. Watermark messages, encryption keys and nonces, target-model initial noise, and target-model inversion outputs are restricted to evaluation. Candidate images are fixed before their target scores are computed. This workflow separates the computational roles and their inputs; the implementation uses a shared operating-system account and does not provide permission isolation.

The evaluated endpoint is ordinary Gaussian Shading (GS) detection, together with decoded-message accuracy, distortion relative to the cover, and computation time. Gaussian Shading embeds a message through the initial noise and recovers it through inversion and decoding [1]. Ordinary detection is one component of the broader forgery question. Semantic content preservation and acceptance by complete content-binding or geometry defenses require their own evidence. Those outcomes remain unknown in this study.

## Compared objectives

Let \(r\) and \(c\) denote the reference and cover images. Let \(E_s\), \(D_s\), and \(I_s\) denote proxy VAE encoding, VAE decoding, and diffusion inversion, respectively. We use \(C\) for the fixed pixel-range conversion and clipping operation, and \(Q\) for the conversion to the exported 8-bit image. The shared reference target is

\[
q_r=I_s(E_s(r)).
\]

The native Imprint objective optimizes a latent variable initialized from the cover, \(z_0=E_s(c)\), by minimizing

\[
L_{\mathrm{native}}(z)=\operatorname{mean}\big[(I_s(z)-q_r)^2\big].
\]

This comparison retains the inversion-matching mechanism of Imprint [2]. The delivery-path candidate inserts the differentiable decode, clip, and encode path into that objective:

\[
R_s(z)=E_s(C(D_s(z))),\qquad
L_{\mathrm{delivery}}(z)=\operatorname{mean}\big[(I_s(R_s(z))-q_r)^2\big].
\]

Both variants use ten Adam updates with learning rate 0.01, the same cover initialization, and the same reference target. Proxy inversion uses 50 steps, an empty prompt, and guidance scale 1. The final output is the single image \(x=Q(C(D_s(z_{10})))\); no intermediate candidate is selected by target scores. The optimization objective is continuous. Its derivative does not differentiate the discrete 8-bit quantizer. Evaluation rereads the exported PNG so that reported detection and distortion correspond to the image actually delivered.

The ten-update point is a low-budget development screen. The Imprint paper optimizes for 150 updates and reports 50-, 100-, and 150-update results in Table 1 [2, §4.2]. This screen does not establish a comparison against that full performance curve. It retains its frozen budget; subsequent method comparisons require matched actual computation on previously unseen tasks.

The delivery implementation computes the continuous composition gradient in two parts. It first differentiates the inversion loss with respect to a detached encoded latent \(u=R_s(z)\), then recomputes \(R_s(z)\) and propagates that gradient through the decode–clip–encode mapping. This applies the chain rule to the specified deterministic continuous computation while avoiding simultaneous retention of both computation graphs. It is an implementation of the stated objective, not a guarantee of transfer to the target model.

The third comparator adapts the single-image VAE-matching core of Jain et al. [3] to the same SD2.1 proxy. Its frozen configuration uses 447 updates, \(\lambda=10000\), \(\alpha=5/255\), and zero initial perturbation. Upstream VAE parameter-gradient flags are retained. The update count follows earlier resource calibration in this project. This comparator is explicitly a short-budget adaptation; it does not reproduce the original paper's complete model and optimization settings. Equal update counts for the two Imprint variants also do not establish equal computation. We measure actual core time and apply the frozen time-ratio criterion below.

## Development design

The target is Stable Diffusion XL base 1.0 at revision `462165984030d82259a11f4367a4eed129e94a7b`. The proxy is the local SD2.1 base snapshot at revision `0094d483a120f3f33dafbd187ea4aa60d10de75c`. Images have resolution 512 by 512 and model computation uses float32. Reference and cover generation use 50 DDIM steps and guidance scale 7.5. Target evaluation uses 50 DDIM inversion steps, an empty prompt, and guidance scale 1.

The frozen design contains four reference/cover prompt groups with three seeded replicas per group. The requested cover contents are a bicycle, a lighthouse, a violin, and a cat; each is paired with a different reference content. A separate GS encryption state is assigned to each reference. The twelve tasks are shared by all three methods. These are development tasks used to screen a specific candidate, rather than a held-out confirmation benchmark. Replicas share prompt groups, so twelve task-level observations do not justify treating all variation as independent population sampling.

GS uses a 32-byte message, 64 replications, \(l=1\), and offset 0. The fixed decision is strict: a candidate passes when message bit accuracy is greater than 0.70703125. Equality is a rejection. We report pass counts and continuous message accuracy separately. Pixel MSE is calculated between reread RGB PNGs in [0,1], and PSNR uses data range 1. Pixel distance is not a formal semantic-content label.

The primary comparison is delivery-path versus native Imprint, paired by task. The candidate is retained for independent confirmation only if all twelve references pass GS, delivery produces at least three additional GS passes, the median within-task pixel-MSE ratio (delivery/native) is at most 1.05, and the median within-task core-time ratio is at most 1.15. All four requirements were frozen before the first model execution. Complete evidence that fails the rule closes this fixed candidate; missing required evidence yields an inconclusive outcome. The decision is a development screening rule, not a statistical-significance test.

The original launch stopped when the preimport device-idle check rejected task 2's Jain process. That process produced no candidate. Its failed execution record is retained, and it was not replaced or retried. The continuation reused the nine successfully completed original processes and ran only work that had never started. The completed comparison contains 35 candidate images, 12 reference images, and 12 cover images, giving 59 target inversions. All twelve primary delivery/native pairs are available. Jain retains a twelve-attempt denominator, with conditional summaries over its eleven delivered images identified explicitly. This missingness is an engineering event, not evidence that Jain's watermark objective failed.

## Completed evidence: reference recovery and image delivery

A preceding closed diagnostic evaluated a fixed source-trained correction of proxy-inverted reference noise. On eight target-generator references, mean latent-bit error decreased from 0.43940735 to 0.43641663, and mean decoded-message accuracy increased from 0.82958984 to 0.83935547. These are reference-recovery measurements, before an image is regenerated and inverted by the target evaluator.

The following fixed paired delivery study generated images from the baseline and corrected representations under matched generation randomness. It sealed all sixteen candidates before evaluating them. The saved verification record independently decoded all 24 reference and candidate scores. Mean target message accuracy was 0.93701172 for baseline delivery and 0.88281250 for corrected delivery, a paired change of -0.05419922. Accuracy decreased in seven pairs and tied in one; none improved. Every reference had accuracy 1.0. Both delivery conditions nevertheless passed ordinary GS on all eight tasks. Thus, the discrete pass count concealed a decrease in the continuous message-accuracy endpoint.

Table 1. Closed eight-pair delivery diagnostic. Accuracy is a fraction of message bits; the change is corrected minus baseline. These are descriptive development results from four prompt groups, with two replicas per group.

| Endpoint | Baseline | Corrected | Paired change |
|---|---:|---:|---:|
| Mean target message accuracy | 0.93701172 | 0.88281250 | -0.05419922 |
| Ordinary GS pass count | 8/8 | 8/8 | 0 |
| Pairs with higher message accuracy after correction | — | 0/8 | — |
| Pairs with unchanged message accuracy | — | 1/8 | — |
| Pairs with lower message accuracy | — | 7/8 | — |

![Paired delivered-image accuracy and changes](../reports/27_recovery_audit_20261019/delivery_endpoint.png)

Figure 1. Delivered-image message accuracy for every pair in the closed diagnostic. Colors denote the four prompt groups; circles and squares distinguish replicas in panel a. All scores exceed the strict GS threshold despite seven negative paired changes. Panel b reports percentage-point differences. The underlying saved rows, plotting code, and source hash are provided with [the figure manifest](../reports/27_recovery_audit_20261019/figure_manifest.json).

The recovery and delivery measurements concern different points in the image pipeline. Their contrast supports a narrow empirical conclusion: improvement in this proxy reference-recovery metric did not predict an improvement in delivered-image message accuracy for the fixed mapping and tasks tested. The mapping was closed under its predeclared nonpositive-endpoint rule. These results motivate measuring complete delivered images in the new method comparison, but they do not establish that the delivery-path Imprint candidate will be effective.

## Complete method comparison

All 35 available candidates were sealed before the three target-evaluation batches. Evaluation completed on 19 October 2026 at 21:16:52 UTC, with 59 scored images. All twelve references passed GS. A server-side CPU decoder checked all 59 scores using evaluator-private state; a separate local rerun of the public analyzer verified candidate/input bindings, preserved failures, evaluation ordering, pixel metrics, timings and summaries. That local check did not independently decrypt messages or load models.

Table 2. Complete development screen. Detection counts use all twelve planned attempts. Mean accuracy, median pixel MSE and median core time condition on delivered candidates: twelve for native and delivery-path Imprint, eleven for adapted Jain. Core time excludes model loading and includes the method-specific preparation and optimization recorded by the frozen protocol.

| Method | Delivered | Ordinary GS passes / attempts | Mean message accuracy | Median pixel MSE | Median core time (s) |
|---|---:|---:|---:|---:|---:|
| Native Imprint | 12/12 | 8/12 | 0.73014323 | 0.00138170 | 377.159 |
| Adapted Jain | 11/12 | 3/12 | 0.65447443 | 0.00058490 | 376.594 |
| Delivery-path Imprint | 12/12 | 6/12 | 0.71191406 | 0.00130111 | 396.505 |

Delivery-path Imprint lost two passes relative to native Imprint, on tasks 5 and 7, and gained none. Its message accuracy was lower in ten pairs and higher in two, with a mean paired difference of -0.01822917, or -1.823 percentage points. Pixel MSE was lower in all twelve pairs. The median within-task MSE ratio was 0.90897063, and the median core-time ratio was 1.05165976. These paired ratios are not ratios of the marginal medians in Table 2.

| Frozen requirement | Observed result | Gate |
|---|---:|---|
| All twelve references valid | 12/12 | Pass |
| At least three additional GS passes versus native Imprint | -2 | Fail |
| Median paired pixel-MSE ratio at most 1.05 | 0.90897063 | Pass |
| Median paired core-time ratio at most 1.15 | 1.05165976 | Pass |

The fixed candidate therefore closes under the predeclared rule. Its lower pixel distortion did not compensate for reduced ordinary GS detection, and the additional computation did not produce the required detection gain. This is complete negative evidence for the specified ten-update candidate on these development tasks. It does not identify a causal explanation or establish that every reconstruction-aware objective must fail.

![Complete method comparison](../reports/27_recovery_audit_20261019/method_comparison_results.png)

Figure 2. Final PNG message accuracy, cover distortion, measured core time and all-attempt accounting. Shading groups the three replicas belonging to each prompt pair. Jain task 2 remains missing and is shown as an engineering failure in the attempt panel. The dashed threshold is strict; equality rejects. The figure was copied byte-for-byte from the original experiment owner's completed publication and visually checked. Its provenance and the local public-analysis rerun are recorded in [final closeout evidence](../reports/27_recovery_audit_20261019/final_closeout.json).

## Limitations and claim scope

The study covers one proxy/target pair, one ordinary watermark detector, and a small set of development prompt groups. The Jain adaptation changes its original computational budget and proxy. Formal human content labels and complete geometry or semantic-binding defense decisions remain unavailable. This failed screen closes the specified candidate; it should not be generalized to population attack success or untested defenses. Further method research requires a distinct, testable computational advantage, matched-cost comparisons and independent tasks rather than tuning this closed candidate against the observed scores.

## Evidence and references

The numerical design is [protocols/27_method_design.json](../protocols/27_method_design.json). The evaluated code is [method_comparison/attack.py](../scripts/method_comparison/attack.py) with the original cores in [cover_pilot/attack.py](../scripts/cover_pilot/attack.py). The reference-recovery record is [stage24](../reports/24_cross_generator/report.md), and the completed delivery values are in [stage25 verification](../reports/25_delivery_transfer/verification.json). The independent continuation audit is [remote_provenance.json](../reports/27_recovery_audit_20261019/remote_provenance.json); it verifies provenance, not scientific efficacy.

Final evidence is available in the [original owner's complete report at commit 6784879](https://github.com/liylei666-hub/watermark2/blob/678487991fab34650cc5b16e5e96a008fb38bcf4/reports/27_method_resume_20261019T173017Z/report.md), [all 36 task rows](../reports/27_recovery_audit_20261019/final_task_results.csv), and [local public-analysis recheck](../reports/27_recovery_audit_20261019/final_public_recheck.json). The preserved failure has no numerical score. Novelty, full-defense acceptance and formal content acceptance remain unestablished.

1. Yang et al. *Gaussian Shading: Provable Performance-Lossless Image Watermarking for Diffusion Models*. 2024. [Primary paper](https://arxiv.org/abs/2404.04956).
2. Müller et al. *Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models*. CVPR 2025. [Primary paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Muller_Black-Box_Forgery_Attacks_on_Semantic_Watermarks_for_Diffusion_Models_CVPR_2025_paper.pdf); [author version, §4.2 and Table 1](https://arxiv.org/html/2412.03283v2).
3. Jain et al. *Forging and Removing Latent-Noise Diffusion Watermarks Using a Single Image*. arXiv:2504.20111v1, 2025. [Primary paper](https://arxiv.org/abs/2504.20111v1).
