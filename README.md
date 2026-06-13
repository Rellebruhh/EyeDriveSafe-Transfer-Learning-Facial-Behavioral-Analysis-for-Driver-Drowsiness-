## Repository Structure

* `model/` - Contains the compiled Edge Impulse model (`.eim` float32) for direct deployment.
* `src/` - Contains the Python inference backend, local Flask dashboard, and Arduino C++ control logic.
* `hardware/` - 3D printing files (STL) for the enclosure and circuit wiring diagrams.
* `docs/` - Consent forms, full research paper, and evaluation metrics.

# EyeDriveSafe

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.xxxxxxx.svg)](https://doi.org/10.5281/zenodo.xxxxxxx)

## Overview
EyeDriveSafe is a portable, IoT-enabled driver drowsiness detection and monitoring system. It uses a transfer learning-based facial behavioral analysis pipeline deployed on an edge computing device. The system detects driver fatigue in real-time using whole-frame binary classification and translates visual cues into an escalating three-tier alert state machine (AWAKE, WARNING, ALERT).

## Key Features
* **Edge AI Inference:** Powered by MobileNetV2 0.35 running locally on an Arduino Uno Q.
* **Custom Metrics:** Computes Drowsy Frame Ratio (DFR) and Drowsy Episode Count (DEC) via a rolling temporal window.
* **IoT Integration:** MQTT-based synchronization with Arduino IoT Cloud for remote tracking.
* **Local Web Dashboard:** Real-time data streaming and threshold calibration via Flask and Socket.IO.
* **LLM Fatigue Reports:** Automated post-session driver fatigue analysis generated via GPT-4.1-mini.

## Hardware Components
* Arduino Uno Q (Microprocessor & STM32 MCU)
* USB Web Camera
* Arduino Modulino Buzzer (QWIIC interface)
* Arduino Modulino Pixels / LED (QWIIC interface)
* USB Type-C Hub
* Custom 3D Printed Enclosure

## Software & Technologies
* **Model Training:** Edge Impulse (MobileNetV2 0.35, 96x96 grayscale input)
* **Edge Deployment:** Arduino IDE (C++)
* **Backend Inference:** Python 3.13
* **Local Dashboard:** Flask, Socket.IO
* **Cloud & Reporting:** Arduino IoT Cloud, GitHub Models API (GPT-4.1-mini)
## Model Performance & Specifications
* **Architecture:** MobileNetV2 0.35
* **Validation Accuracy:** 97.7%
* **AUC-ROC:** 0.98
* **Inference Time:** 13 ms
* **Peak RAM Usage:** 1.1 MB
* **Flash Usage:** 2.0 MB

## State Machine Logic
1.  **AWAKE:** Default state. Resets after 0.5s of awake classification.
2.  **WARNING:** Triggered after 1.5s of sustained drowsy frames (Yellow LED).
3.  **ALERT:** Triggered after 3.0s total of sustained drowsy frames (Red LED + Buzzer).

## Installation & Deployment

### 1. Model Setup (Arduino Uno Q)
This repository includes the pre-trained MobileNetV2 model exported directly from Edge Impulse. We utilize the unquantized `float32` `.eim` file to retain maximum classification precision, which operates efficiently within the hardware constraints of the Arduino Uno Q (13 ms inference time, 1.1MB peak RAM).

**To run the model locally:**
1. Navigate to the `model/` directory in this repository and download the `float32` `.eim` file.
2. Ensure your Arduino Uno Q is connected to your machine and the USB web camera is routed through the Type-C hub.
3. Use the [Edge Impulse CLI](https://docs.edgeimpulse.com/docs/edge-impulse-cli/cli-installation) to deploy the model:
   
   edge-impulse-run-impulse --bin-file path/to/your/downloaded_model.eim

### 2. Dashboard & IoT Integration
1. **Local Web Dashboard:** Execute the Flask application (`src/`) to initialize the local server with Socket.IO. This enables real-time visualization of detection outputs and allows adjustment of the confidence threshold slider without retraining the model.
2. **Cloud Synchronization:** Connect the Arduino Uno Q to Wi-Fi to activate MQTT transmission to the Arduino IoT Cloud. This allows remote tracking of the Alert State, Drowsy Frame Ratio (DFR), Drowsy Episodes, and Alert Count.
3. **AI Fatigue Reporting:** Upon session completion, the system utilizes the GitHub Models API (GPT-4.1-mini) to generate and deliver an automated post-session fatigue analysis report via the Arduino IoT Cloud Messenger widget.

## Authors
Jonrelle Mae B. Gabrinao, Anwar G. Abdullah, Jarell S. Alegre, Fernando Miguel T. Cantor, Dongjin M. Constante, James Brian B. Engay, Azriel Henrix J. Erfe, Eugenio Dave A. Tamiao.
*Taguig Science High School*

## Citation
To cite this research or repository, please use the Zenodo DOI link provided at the top of this document.
