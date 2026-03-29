# Architecture

OpenDream adds a lifecycle layer with three parts:

1. manifest rendering and installation
2. durable worker heartbeat plus runtime status
3. operator-facing service control, doctor, and autowire surfaces

Only OpenDream-owned state, manifests, and managed adapter blocks may be mutated.
