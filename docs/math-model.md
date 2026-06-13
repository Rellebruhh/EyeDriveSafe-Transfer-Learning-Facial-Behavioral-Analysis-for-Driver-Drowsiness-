# Mathematical Modeling of Drowsiness Metrics

The EyeDriveSafe system processes discrete video frames and outputs binary classification to optimize computational efficiency on portable hardware. This requires a mathematical translation from the continuous time domain of standard clinical metrics to a discrete sequential space.

## 1. Foundational Metric: PERCLOS
The standard PERCLOS computation over a video sequence is given by:

$$P=\frac{E_{c}}{E_{t}}$$

Where $E_{c}$ is the count of frames classified as eyes-closed and $E_{t}$ is the total frame count within the observation interval.

## 2. Derivation of Drowsy Frame Ratio (DFR)
To adapt PERCLOS for whole-face binary classification, the 80% pupil coverage criterion is replaced with a discrete frame-level classification output. Let $d(i)$ represent the discrete classification for frame $i$:

$$d(i)=1 \text{ if } P(drowsy|frame_{i})\ge T$$
$$d(i)=0 \text{ otherwise}$$

Where $T$ is the user-configurable confidence threshold (default $T=0.50$). For a rolling temporal window containing $N$ total frames, the DFR translates the continuous PERCLOS formula into a discrete mathematical ratio:

$$DFR=\frac{1}{N}\sum_{i=1}^{N}d(i)$$

## 3. Derivation of Drowsy Episode Count (DEC)
The system tracks discrete drowsy episodes by isolating classification transitions that violate a specific duration threshold. Let $d(t)$ represent the drowsiness state classification at time $t$. An episode is detected, and the DEC increments, when the following transition sequence occurs:

* $d(t_{onset})$ transitions from $0\rightarrow1$
* $d(t_{offset})$ transitions from $1\rightarrow0$

Subject to the physiological eye blink maximum duration constraint $B$ (where $B=0.6$ seconds):

$$t_{offset}-t_{onset}\le B$$

Transitions exceeding $B$ indicate prolonged drowsiness. Episode frequency over the rolling window is computed as:

$$EF(t)=\frac{E_{w}}{W}\times60$$

Where $E_{w}$ is the count of qualifying episodes within window $W$ (in seconds), normalized to episodes per minute.
