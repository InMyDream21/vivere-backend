<div align="center">
  
# Vivere: Reminiscence Therapy Companion App (iPad Only)

![Platform](https://img.shields.io/badge/Platform-iPad-blue)
![iOS](https://img.shields.io/badge/iOS-17.6%2B-lightgrey)
![Swift](https://img.shields.io/badge/Swift-5.9-orange)
![Xcode](https://img.shields.io/badge/Xcode-16-blue)

![License](https://img.shields.io/badge/license-MIT-green)
[![Backend Repo](https://img.shields.io/badge/Backend-Repo-black)](https://github.com/Vivere-by-NetiZen/vivere-backend)
[![TestFlight](https://img.shields.io/badge/TestFlight-Link-lightblue)](https://testflight.apple.com/join/6fr2sVeB)

</div>

<br>

Vivere is a specialized iOS application designed to support structured reminiscence therapy for older adults with early to mild dementia and their caregivers or companions. The app helps caregivers enhance communication and cognitive well-being by evoking and utilizing meaningful memories from the elder's past.


---

## Features

- Memory Collection: A private space to upload, organize, and revisit personal photos and videos that spark meaningful recollections.
- Puzzle and Flip-Card Games: Gentle and engaging warm-up activities designed to help older adults prepare for deeper reminiscence sessions.
- Moving Picture Feature: Bring static photos to life, making memories more vivid and emotionally engaging.
- AI Companion for Caregivers: An AI assistant that provides tailored communication guidance based on the elder's responses, helping caregivers navigate conversations more effectively.

---

## Tech Stack

### Frontend (iOS App) ([Separate Repository](https://github.com/Vivere-by-NetiZen/vivere-app))
Language: Swift  
Architecture: MVVM  
Frameworks and Technologies:  
- SwiftUI: Primary UI layer  
- UIKit: Used for specific functionalities  
- AVKit and AVFoundation: Speech and audio processing  
- Photos and PhotosUI: Media importing and handling  
- SwiftData: Local structured data storage  
- Combine and Observation: Reactive state management  
- Foundation: Core utilities

<br>

### Backend
Language: Python  
Framework: FastAPI  
AI Technologies: Gemini, Veo, Google Cloud Speech-to-Text  
Runtime: Local machine execution  
Remote Access: Tailscale for secure cross-device connectivity

---

## Installation

Vivere is an iPad-only application.  
You can install it using TestFlight or build it locally with Xcode.

### Option A: TestFlight (Recommended)
Install via [TestFlight](https://testflight.apple.com/join/6fr2sVeB)

<br>

### Option B: Clone and Build
Requirements:  
- Xcode 16 or newer  
- iPadOS 17.6 or newer  
- A physical iPad or iPad simulator support

Steps:
```bash
git clone https://github.com/Vivere-by-NetiZen/vivere-app
cd vivere-app
open .
```
Build and run in Xcode on an iPad device or iPad simulator.

---

## Usage

After installing the app, users can:
  
1. Upload photos or videos to support reminiscence
2. Play puzzle and flip-card games as warm-up activities
3. See animated photos after completing a game
4. Use the AI Companion to support meaningful caregiver-elder communication

---

## Screenshots

Screenshots or demo media will be added here.

---

## Team

| Name | Role | Responsibilities |
|------|-------|------------------|
| [Aulia Nisrina R.](linkedin.com/in/aulianisrina/) | Product Manager | Planning, coordination, and product direction |
| [Grace Maria Y. A. G.](https://www.linkedin.com/in/grace-maria-22a910246) | Designer | UI/UX design, Interaction flows |
| [Ali Jazzy R.](https://www.linkedin.com/in/alijazzy) | Designer | UI/UX design, Interaction flows |
| [Reinhart C.](https://github.com/reinhart-c) | Tech Lead | Architecture, Code standards, Technical decisions, Feature development, UI implementation |
| [Imo Madjid](https://github.com/MassiveMassimo) | Tech Engineer | Server setup, Feature development, UI implementation |
| [Ahmed N. Haikal]() | Tech Engineer | Backend integration, AI integration, UI implementation |

---

## Privacy

This project follows the data-handling rules described in [PRIVACY.md](PRIVACY.md) file.

---

## License

This project is licensed under the terms described in the [LICENSE.md](LICENSE.md) file.
