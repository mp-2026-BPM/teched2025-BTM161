"""
CSS styles for the coffee shop chat interface.
"""

ENHANCED_CSS = """
.jp-OutputArea-output pre {
    white-space: pre-wrap !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    max-width: 100% !important;
}
.widget-output pre {
    white-space: pre-wrap !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    max-width: 100% !important;
}
.output_subarea pre {
    white-space: pre-wrap !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    max-width: 100% !important;
}

/* Enhanced chat styling */
.chat-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.input-area {
    border-top: 1px solid #e0e0e0;
    padding: 5px;
}

.default-input input[type='text'] {
    height: 100% !important;
}

.default-button {
    transition: all 0.2s ease;
    border-radius: 8px;
    height: 35px;
    width: 150px;
}

.scenario-area {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    border-left: 4px solid #007bff;
    margin: 10px 0;
    flex: 1;
}

.default-button:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.controls-container {
    gap: 20px;
    display: flex;
    align-items: stretch;
    margin-top: 15px;
}

.button-group {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.status-indicator {
    margin-left: 10px;
    flex-grow: 0;
    width: 250px;
}

.input-line {
    flex-grow: 1;
}

.chat-area {
    border: 2px solid #e0e0e0;
    border-radius: 10px;
    overflow: hidden;
}

.tool-output .tool-output-label {
    color: #6c757d;
    font-size: 11px;
}

.tool-output pre.tool-output-code {
    background-color: #ffffff;
    line-height: 1.1;
    padding: 8px;
    font-family: monospace;
    font-size: 8pt;
    overflow-x: auto;
    white-space: pre-wrap;
    border-radius: 4px;
    border-left: 3px solid #28a745;
}

.chat-output {
    width: 100%;
    height: 450px;
    overflow: auto;
    padding: 15px;
    background-color: #fafafa;
}

.chat-output.chat-silent-mode .chat-bubble.chat-verbose-message {
    display: none !important;
}

.chat-notification {
    background: linear-gradient(45deg, #d4edda, #a3d977);
    border: 1px solid #28a745;
    border-radius: 10px;
    padding: 15px;
    margin: 10px 0;
    text-align: center;
}

.chat-notification h4 {
    margin: 0;
    color: #155724;
}

/* Scrollbar styling for chat output */
.chat-output::-webkit-scrollbar {
    width: 8px;
}

.chat-output::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

.chat-output::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
}

.chat-output::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
}
"""
