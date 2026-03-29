# Installation flow

1. validate workspace, memory root, and executable path
2. render a supervisor manifest from the package templates
3. write the rendered manifest under OpenDream state
4. copy the installable unit or plist to the selected install root
5. optionally start the service
6. emit a machine-readable install report
