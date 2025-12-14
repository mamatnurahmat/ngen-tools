#!/usr/bin/env python3
import argparse
import json
import os
import sys
import subprocess
import http.server
import socketserver
import threading
import webbrowser
from http import HTTPStatus

def migrate(input_file="apigateway.json", config_dir="config"):
    """
    Migrates apigateway.json to partial configurations.
    """
    
    settings_dir = os.path.join(config_dir, "settings")
    partials_dir = os.path.join(config_dir, "partials")

    # Create directories
    os.makedirs(settings_dir, exist_ok=True)
    os.makedirs(partials_dir, exist_ok=True)

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{input_file}': {e}")
        sys.exit(1)

    endpoints = data.get('endpoints', [])
    endpoint_count = len(endpoints)
    print(f"Processing {endpoint_count} endpoints...")

    # 1. Generate global_extra_config.tmpl
    # Logic: dump extra_config and strip first/last lines (braces)
    extra_config = data.get('extra_config', {})
    extra_config_str = json.dumps(extra_config, indent=2)
    # Split into lines, remove first and last
    extra_config_lines = extra_config_str.split('\n')
    if len(extra_config_lines) >= 2:
        inner_lines = extra_config_lines[1:-1]
        tmpl_content = '\n'.join(inner_lines)
    else:
        tmpl_content = "" # Empty or single line weirdness
    
    with open(os.path.join(partials_dir, "global_extra_config.tmpl"), 'w') as f:
        f.write(tmpl_content + "\n")

    # 2. Generate service.json
    service_data = {
        "name": data.get("name"),
        "port": data.get("port"),
        "cache_ttl": data.get("cache_ttl"),
        "timeout": data.get("timeout")
    }
    with open(os.path.join(settings_dir, "service.json"), 'w') as f:
        json.dump(service_data, f, indent=2)

    # 3. Generate endpoint.json
    mapping_group = []
    for idx, endpoint in enumerate(endpoints):
        # Index is 0-based in loop, but we want 1-based ID
        id_str = str(idx + 1)
        
        # Safely get method and host
        method = endpoint.get("method")
        
        # Access nested host safely: .backend[0].host[0]
        host = None
        private_endpoint = None
        backends = endpoint.get("backend", [])
        if backends and len(backends) > 0:
            hosts = backends[0].get("host", [])
            if hosts and len(hosts) > 0:
                host = hosts[0]
            private_endpoint = backends[0].get("url_pattern")
        
        mapping_group.append({
            "id": id_str,
            "endpoint": endpoint.get("endpoint"),
            "method": method,
            "host": host,
            "private_endpoint": private_endpoint
        })

    with open(os.path.join(settings_dir, "endpoint.json"), 'w') as f:
        json.dump({"mapping_group": mapping_group}, f, indent=2)

    # 4. Generate individual endpoint partials
    for idx, endpoint in enumerate(endpoints):
        idx_1_based = idx + 1
        outfile = os.path.join(partials_dir, str(idx_1_based))
        with open(outfile, 'w') as f:
            json.dump(endpoint, f, indent=2)
        
        endpoint_url = endpoint.get("endpoint", "")
        # Remove leading slash for display to match shell partials
        display_url = endpoint_url.lstrip('/')
        print(f"  {idx_1_based} => ENDPOINT: {display_url}")

    print(f"Configuration generated successfully in {config_dir}/")

# --- Web Server Implementation ---

class APIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # Handle API calls
        if self.path in ['/api/create', '/api/update', '/api/delete']:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                
                if self.path == '/api/create':
                    # Create endpoint
                    # data is now the full JSON object
                    new_id = create_endpoint(
                        self.server.config_dir,
                        data
                    )
                    response = {"success": True, "id": new_id, "message": "Endpoint created successfully"}
                    
                elif self.path == '/api/update':
                    # Update endpoint
                    modify_endpoint(
                        self.server.config_dir,
                        data.get('id'), # ID is still separate for clarity/safety
                        full_data=data # Pass full data
                    )
                    response = {"success": True, "message": f"Endpoint {data.get('id')} updated"}
                    
                elif self.path == '/api/delete':
                    # Delete endpoint
                    remove_endpoint(
                        self.server.config_dir,
                        data.get('id')
                    )
                    response = {"success": True, "message": f"Endpoint {data.get('id')} deleted"}
                
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                error_response = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
            return

        # Handle check API
        if self.path == '/api/check':
            try:
                results = check_krakend(config_dir=self.server.config_dir)
                all_success = all(r["success"] for r in results)
                response = {
                    "success": all_success,
                    "results": results
                }
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                error_response = {"success": False, "error": str(e)}
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
            return

        super().do_POST()

    def do_GET(self):
        # Serve root: List of endpoints
        if self.path == '/' or self.path == '/index.html':
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_endpoint_list_html().encode('utf-8'))
            return
        
        # Serve details: /details/<id> (HTML View)
        if self.path.startswith('/details/'):
            endpoint_id = self.path.split('/')[-1]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_endpoint_detail_html(endpoint_id).encode('utf-8'))
            return

        # Serve details: /api/detail/<id> (JSON Data)
        if self.path.startswith('/api/detail/'):
            endpoint_id = self.path.split('/')[-1]
            partial_file = os.path.join(self.server.config_dir, "partials", endpoint_id)
            try:
                with open(partial_file, 'r') as f:
                    content = f.read() # Read raw to return exactly what is there
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        # Fallback to default behavior (serving files if needed, or 404)
        super().do_GET()

    def get_endpoint_list_html(self):
        endpoint_file = os.path.join(self.server.config_dir, "settings/endpoint.json")
        try:
            with open(endpoint_file, 'r') as f:
                data = json.load(f)
                endpoints = data.get("mapping_group", [])
        except Exception as e:
            return f"<h1>Error loading endpoints</h1><p>{e}</p>"

        rows = ""
        for ep in endpoints:
            ep_id = ep.get('id', 'N/A')
            method = ep.get('method') or 'GET'  # Handle None
            url = ep.get('endpoint', 'N/A') or 'N/A'
            host = ep.get('host', 'N/A') or 'N/A'
            private_endpoint = ep.get('private_endpoint', 'N/A') or 'N/A'
            
            # Read partial file for extra details
            extra_config = False
            input_headers = []
            input_query_strings = []
            partial_file = os.path.join(self.server.config_dir, "partials", str(ep_id))
            try:
                with open(partial_file, 'r') as f:
                    partial_data = json.load(f)
                    extra_config = bool(partial_data.get('extra_config'))
                    input_headers = partial_data.get('input_headers', [])
                    input_query_strings = partial_data.get('input_query_strings', [])
            except:
                pass
            
            # Format for display
            extra_config_display = '<span class="badge badge-yes">Yes</span>' if extra_config else '<span class="badge badge-no">No</span>'
            headers_display = ', '.join(input_headers) if input_headers else '-'
            query_display = ', '.join(input_query_strings) if input_query_strings else '-'
            
            rows += f"""
            <tr onclick="window.location='/details/{ep_id}'">
                <td class="id-col">{ep_id}</td>
                <td><span class="method {method.lower()}">{method}</span></td>
                <td class="code-font" title="{url}">{url}</td>
                <td class="code-font" title="{private_endpoint}">{private_endpoint}</td>
                <td class="code-font">{host}</td>
                <td class="center-col">{extra_config_display}</td>
                <td class="code-font small-text" title="{headers_display}">{headers_display}</td>
                <td class="code-font small-text" title="{query_display}">{query_display}</td>
                <td class="actions-col" onclick="event.stopPropagation()">
                    <button class="btn-icon edit" onclick="loadEndpointForEdit('{ep_id}')">✎</button>
                    <button class="btn-icon delete" onclick="deleteEndpoint('{ep_id}')">✕</button>
                </td>
            </tr>
            """

        return self.get_html_template("API Gateway Endpoints", f"""
            <!-- Collapsible Editor Panel -->
            <div class="editor-panel" id="editorPanel">
                <div class="editor-toggle" onclick="toggleEditor()">
                    <span class="toggle-icon" id="toggleIcon">▶</span>
                    <h3 id="editorTitle">Create New Endpoint</h3>
                    <input type="hidden" id="epId">
                </div>
                <div class="editor-content" id="editorContent" style="display: none;">
                    <div id="editor-container" style="height: 350px; width: 100%; border: 1px solid var(--border); border-radius: 6px;"></div>
                    <div id="validationError" class="validation-error" style="display: none;"></div>
                    <div class="editor-actions">
                        <button class="btn-secondary" onclick="resetEditor()">Reset</button>
                        <button class="btn-primary" onclick="saveEndpoint()">💾 Save</button>
                    </div>
                </div>
            </div>

            <!-- cURL Web Editor Panel -->
            <div class="editor-panel" id="curlPanel">
                <div class="editor-toggle curl-toggle" onclick="toggleCurlEditor()">
                    <span class="toggle-icon" id="curlToggleIcon">▶</span>
                    <h3>🖥️ cURL Builder & Tester</h3>
                </div>
                <div class="editor-content" id="curlContent" style="display: none;">
                    <div class="curl-builder">
                        <!-- Request URL Row -->
                        <div class="curl-url-row">
                            <select id="curlMethod" class="curl-method-select">
                                <option value="GET">GET</option>
                                <option value="POST">POST</option>
                                <option value="PUT">PUT</option>
                                <option value="DELETE">DELETE</option>
                                <option value="PATCH">PATCH</option>
                            </select>
                            <input type="text" id="curlUrl" class="curl-url-input" placeholder="/api/v1/endpoint" value="/health">
                            <button class="btn-send" onclick="executeCurl()">
                                <span id="sendBtnText">▶ Send</span>
                            </button>
                        </div>
                        
                        <!-- Base URL Info -->
                        <div class="curl-base-url">
                            <span class="base-label">Base URL:</span>
                            <code id="baseUrl">http://localhost:8005</code>
                            <button class="btn-tiny" onclick="editBaseUrl()">✎</button>
                        </div>
                        
                        <!-- Tabs -->
                        <div class="curl-tabs">
                            <button class="curl-tab active" onclick="switchCurlTab('headers')">Headers</button>
                            <button class="curl-tab" onclick="switchCurlTab('body')">Body</button>
                            <button class="curl-tab" onclick="switchCurlTab('curl')">cURL</button>
                        </div>
                        
                        <!-- Headers Tab -->
                        <div class="curl-tab-content" id="tab-headers">
                            <div id="headersContainer">
                                <div class="header-row">
                                    <input type="text" placeholder="Header Name" value="Content-Type" class="header-key">
                                    <input type="text" placeholder="Header Value" value="application/json" class="header-value">
                                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                                </div>
                                <div class="header-row">
                                    <input type="text" placeholder="Header Name" value="Authorization" class="header-key">
                                    <input type="text" placeholder="Header Value" value="Bearer token" class="header-value">
                                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                                </div>
                            </div>
                            <button class="btn-add-header" onclick="addHeader()">+ Add Header</button>
                        </div>
                        
                        <!-- Body Tab -->
                        <div class="curl-tab-content" id="tab-body" style="display: none;">
                            <textarea id="curlBody" class="curl-body-textarea" placeholder='{{"key": "value"}}'></textarea>
                        </div>
                        
                        <!-- cURL Tab -->
                        <div class="curl-tab-content" id="tab-curl" style="display: none;">
                            <div class="curl-command-container">
                                <pre id="curlCommand" class="curl-command">curl -X GET 'http://localhost:8005/health'</pre>
                                <button class="btn-copy-curl" onclick="copyCurlCommand()">📋 Copy</button>
                            </div>
                        </div>
                        
                        <!-- Response Section -->
                        <div class="curl-response" id="curlResponse" style="display: none;">
                            <div class="response-header">
                                <span class="response-title">Response</span>
                                <span class="response-status" id="responseStatus"></span>
                                <span class="response-time" id="responseTime"></span>
                            </div>
                            <pre class="response-body" id="responseBody"></pre>
                        </div>
                    </div>
                </div>
            </div>

            <div class="controls-container">
                <input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Search endpoints, methods, hosts..." class="search-input">
                <div class="header-actions">
                    <span class="stats">{len(endpoints)} Endpoints</span>
                    <button class="btn-download" onclick="downloadCSV()">📥 Download CSV</button>
                    <button class="btn-check" onclick="checkConfig()">🔍 Check Config</button>
                </div>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 40px;">ID</th>
                            <th style="width: 60px;">Method</th>
                            <th style="width: 20%;">Endpoint</th>
                            <th style="width: 20%;">Private Endpoint</th>
                            <th style="width: 12%;">Host</th>
                            <th style="width: 50px;">Extra</th>
                            <th style="width: 15%;">Headers</th>
                            <th style="width: 10%;">Query Strings</th>
                            <th style="width: 60px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="endpointTable">
                        {rows}
                    </tbody>
                </table>
            </div>
            
            <script>
            function searchTable() {{
                var input, filter, table, tr, td, i, j, txtValue, match;
                input = document.getElementById("searchInput");
                filter = input.value.toUpperCase();
                table = document.getElementById("endpointTable");
                tr = table.getElementsByTagName("tr");
                
                for (i = 0; i < tr.length; i++) {{
                    match = false;
                    tds = tr[i].getElementsByTagName("td");
                    for (j = 0; j < tds.length; j++) {{
                        if (tds[j]) {{
                            txtValue = tds[j].textContent || tds[j].innerText;
                            if (txtValue.toUpperCase().indexOf(filter) > -1) {{
                                match = true;
                                break;
                            }}
                        }}
                    }}
                    if (match) tr[i].style.display = "";
                    else tr[i].style.display = "none";
                }}
            }}

            let isEditMode = false;
            let editor = null;
            let editorInitialized = false;
            
            const defaultTemplate = {{
                "endpoint": "/api/v1/resource",
                "method": "GET",
                "output_encoding": "no-op",
                "input_headers": ["Authorization", "Content-Type"],
                "backend": [{{
                    "url_pattern": "/internal/resource",
                    "host": ["service:8080"]
                }}]
            }};
            
            function initEditor() {{
                if (editorInitialized) return;
                editor = ace.edit("editor-container");
                editor.setTheme("ace/theme/monokai");
                editor.session.setMode("ace/mode/json");
                editor.setOptions({{
                    fontSize: "13px",
                    showPrintMargin: false,
                }});
                
                // Set default template
                editor.setValue(JSON.stringify(defaultTemplate, null, 2), -1);
                
                // Validate on change
                editor.session.on('change', function() {{
                    validateJson();
                }});
                editorInitialized = true;
            }}
            
            function toggleEditor() {{
                const content = document.getElementById("editorContent");
                const icon = document.getElementById("toggleIcon");
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "▼";
                    initEditor();
                    if (editor) editor.resize();
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "▶";
                }}
            }}
            
            function validateJson() {{
                const content = editor.getValue();
                const errorDiv = document.getElementById("validationError");
                try {{
                    JSON.parse(content);
                    errorDiv.style.display = "none";
                    return true;
                }} catch (e) {{
                    errorDiv.textContent = "⚠️ JSON Error: " + e.message;
                    errorDiv.style.display = "block";
                    return false;
                }}
            }}

            function resetEditor() {{
                isEditMode = false;
                document.getElementById("editorTitle").innerText = "Create New Endpoint";
                document.getElementById("epId").value = "";
                editor.setValue(JSON.stringify(defaultTemplate, null, 2), -1);
            }}

            async function loadEndpointForEdit(epId) {{
                // Open and initialize editor first
                const content = document.getElementById("editorContent");
                const icon = document.getElementById("toggleIcon");
                content.style.display = "block";
                icon.textContent = "▼";
                initEditor();
                if (editor) editor.resize();
                
                isEditMode = true;
                document.getElementById("editorTitle").innerText = "Edit Endpoint #" + epId;
                document.getElementById("epId").value = epId;
                
                try {{
                    const response = await fetch("/api/detail/" + epId);
                    if (!response.ok) throw new Error("Failed to fetch detail");
                    const data = await response.json();
                    editor.setValue(JSON.stringify(data, null, 2), -1);
                    
                    // Scroll to editor
                    document.getElementById("editorPanel").scrollIntoView({{ behavior: 'smooth' }});
                }} catch (e) {{
                    alert("Error loading endpoint: " + e.message);
                }}
            }}

            async function saveEndpoint() {{
                if (!validateJson()) {{
                    alert("Please fix the JSON errors before saving.");
                    return;
                }}
                
                const id = document.getElementById("epId").value;
                const content = editor.getValue();
                let data = JSON.parse(content);

                if (isEditMode) {{
                    data.id = id;
                }}

                const url = isEditMode ? "/api/update" : "/api/create";
                
                try {{
                    const response = await fetch(url, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        location.reload();
                    }} else {{
                        alert("Error: " + result.error);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }}
            }}

            async function deleteEndpoint(id) {{
                if (!confirm("Are you sure you want to delete endpoint " + id + "?")) return;
                
                try {{
                    const response = await fetch("/api/delete", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ id: id }})
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        location.reload();
                    }} else {{
                        alert("Error: " + result.error);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }}
            }}

            async function checkConfig() {{
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = "⏳ Checking...";
                
                try {{
                    const response = await fetch("/api/check", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }}
                    }});
                    
                    const result = await response.json();
                    
                    let message = "";
                    if (result.results) {{
                        for (const r of result.results) {{
                            const status = r.success ? "✅" : "❌";
                            message += status + " " + r.step + "\\n";
                            if (r.output) message += r.output + "\\n";
                            if (r.error && !r.success) message += "Error: " + r.error + "\\n";
                        }}
                    }}
                    
                    if (result.success) {{
                        alert("✅ All checks passed!\\n\\n" + message);
                    }} else {{
                        alert("❌ Some checks failed:\\n\\n" + message);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }} finally {{
                    btn.disabled = false;
                    btn.textContent = "🔍 Check Config";
                }}
            }}

            function downloadCSV() {{
                const table = document.querySelector("table");
                const rows = table.querySelectorAll("tr");
                let csv = [];
                
                // Header
                const headers = ["ID", "Method", "Endpoint", "Private Endpoint", "Host", "Extra Config", "Input Headers", "Query Strings"];
                csv.push(headers.join("|"));
                
                // Data rows
                const tbody = document.getElementById("endpointTable");
                const dataRows = tbody.querySelectorAll("tr");
                
                dataRows.forEach(row => {{
                    if (row.style.display === "none") return; // Skip filtered rows
                    
                    const cells = row.querySelectorAll("td");
                    if (cells.length >= 8) {{
                        const rowData = [
                            cells[0].textContent.trim(),  // ID
                            cells[1].textContent.trim(),  // Method
                            cells[2].textContent.trim(),  // Endpoint
                            cells[3].textContent.trim(),  // Private Endpoint
                            cells[4].textContent.trim(),  // Host
                            cells[5].textContent.trim(),  // Extra Config
                            cells[6].textContent.trim(),  // Headers
                            cells[7].textContent.trim()   // Query Strings
                        ];
                        csv.push(rowData.join("|"));
                    }}
                }});
                
                // Create and download file
                const csvContent = csv.join("\\n");
                const blob = new Blob([csvContent], {{ type: "text/csv;charset=utf-8;" }});
                const link = document.createElement("a");
                const url = URL.createObjectURL(blob);
                link.setAttribute("href", url);
                link.setAttribute("download", "endpoints_" + new Date().toISOString().slice(0,10) + ".csv");
                link.style.visibility = "hidden";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}
            
            // cURL Builder functions
            let baseUrl = "http://localhost:8005";
            
            function toggleCurlEditor() {{
                const content = document.getElementById("curlContent");
                const icon = document.getElementById("curlToggleIcon");
                
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "▼";
                    updateCurlCommand();
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "▶";
                }}
            }}
            
            function switchCurlTab(tabName) {{
                // Update tab buttons
                document.querySelectorAll('.curl-tab').forEach(t => t.classList.remove('active'));
                event.target.classList.add('active');
                
                // Show/hide content
                document.querySelectorAll('.curl-tab-content').forEach(c => c.style.display = 'none');
                document.getElementById('tab-' + tabName).style.display = 'block';
                
                if (tabName === 'curl') {{
                    updateCurlCommand();
                }}
            }}
            
            function addHeader() {{
                const container = document.getElementById('headersContainer');
                const row = document.createElement('div');
                row.className = 'header-row';
                row.innerHTML = `
                    <input type="text" placeholder="Header Name" class="header-key">
                    <input type="text" placeholder="Header Value" class="header-value">
                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                `;
                container.appendChild(row);
            }}
            
            function removeHeader(btn) {{
                btn.parentElement.remove();
            }}
            
            function editBaseUrl() {{
                const newUrl = prompt("Enter base URL:", baseUrl);
                if (newUrl) {{
                    baseUrl = newUrl;
                    document.getElementById('baseUrl').textContent = baseUrl;
                    updateCurlCommand();
                }}
            }}
            
            function getHeaders() {{
                const headers = {{}};
                document.querySelectorAll('.header-row').forEach(row => {{
                    const key = row.querySelector('.header-key').value.trim();
                    const value = row.querySelector('.header-value').value.trim();
                    if (key) headers[key] = value;
                }});
                return headers;
            }}
            
            function updateCurlCommand() {{
                const method = document.getElementById('curlMethod').value;
                const url = document.getElementById('curlUrl').value;
                const body = document.getElementById('curlBody').value;
                const headers = getHeaders();
                
                let cmd = `curl -X ${{method}} '${{baseUrl}}${{url}}'`;
                
                Object.keys(headers).forEach(key => {{
                    cmd += ` \\\\\n  -H '${{key}}: ${{headers[key]}}'`;
                }});
                
                if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {{
                    cmd += ` \\\\\n  -d '${{body}}'`;
                }}
                
                document.getElementById('curlCommand').textContent = cmd;
            }}
            
            function copyCurlCommand() {{
                const cmd = document.getElementById('curlCommand').textContent;
                navigator.clipboard.writeText(cmd);
                alert("cURL command copied!");
            }}
            
            async function executeCurl() {{
                const btn = document.querySelector('.btn-send');
                const btnText = document.getElementById('sendBtnText');
                const method = document.getElementById('curlMethod').value;
                const urlPath = document.getElementById('curlUrl').value;
                const body = document.getElementById('curlBody').value;
                const headers = getHeaders();
                
                btn.disabled = true;
                btnText.textContent = "⏳ Sending...";
                
                const startTime = performance.now();
                
                try {{
                    const fetchOptions = {{
                        method: method,
                        headers: headers
                    }};
                    
                    if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {{
                        fetchOptions.body = body;
                    }}
                    
                    const response = await fetch(baseUrl + urlPath, fetchOptions);
                    const endTime = performance.now();
                    const duration = Math.round(endTime - startTime);
                    
                    let responseText;
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {{
                        const json = await response.json();
                        responseText = JSON.stringify(json, null, 2);
                    }} else {{
                        responseText = await response.text();
                    }}
                    
                    // Show response
                    document.getElementById('curlResponse').style.display = 'block';
                    document.getElementById('responseStatus').textContent = response.status + ' ' + response.statusText;
                    document.getElementById('responseStatus').className = 'response-status ' + (response.ok ? 'status-ok' : 'status-error');
                    document.getElementById('responseTime').textContent = duration + 'ms';
                    document.getElementById('responseBody').textContent = responseText;
                    
                }} catch (e) {{
                    document.getElementById('curlResponse').style.display = 'block';
                    document.getElementById('responseStatus').textContent = 'Error';
                    document.getElementById('responseStatus').className = 'response-status status-error';
                    document.getElementById('responseTime').textContent = '';
                    document.getElementById('responseBody').textContent = e.message;
                }} finally {{
                    btn.disabled = false;
                    btnText.textContent = "▶ Send";
                }}
            }}
            
            // Update curl command on input change
            document.addEventListener('DOMContentLoaded', function() {{
                const curlMethod = document.getElementById('curlMethod');
                const curlUrl = document.getElementById('curlUrl');
                const curlBody = document.getElementById('curlBody');
                
                if (curlMethod) curlMethod.addEventListener('change', updateCurlCommand);
                if (curlUrl) curlUrl.addEventListener('input', updateCurlCommand);
                if (curlBody) curlBody.addEventListener('input', updateCurlCommand);
                
                // Update on header changes
                document.getElementById('headersContainer')?.addEventListener('input', updateCurlCommand);
            }});
            </script>
        """)

    def get_endpoint_detail_html(self, endpoint_id):
        partial_file = os.path.join(self.server.config_dir, "partials", endpoint_id)
        
        content = ""
        try:
            with open(partial_file, 'r') as f:
                data = json.load(f)
                content = json.dumps(data, indent=2)
        except Exception as e:
            content = f"Error loading detail: {e}"

        return self.get_html_template(f"Endpoint {endpoint_id} Details", f"""
            <div class="header">
                <h2>Endpoint ID: {endpoint_id}</h2>
                <a href="/" class="back-btn">← Back to List</a>
            </div>
            <div class="detail-container">
                <pre><code class="language-json">{content}</code></pre>
            </div>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
            <script>hljs.highlightAll();</script>
        """)

    def get_html_template(self, title, body):
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.7/ace.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --primary: #2563eb;
                    --primary-hover: #1d4ed8;
                    --bg-page: #f8fafc;
                    --bg-card: #ffffff;
                    --border: #e2e8f0;
                    --text-main: #1e293b;
                    --text-secondary: #64748b;
                    --hover-row: #f1f5f9;
                }}
                body {{ 
                    font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                    background-color: var(--bg-page); 
                    color: var(--text-main); 
                    margin: 0; 
                    padding: 40px; 
                }}
                h1 {{ font-weight: 600; color: var(--text-main); margin-bottom: 24px; font-size: 1.75rem; }}
                
                .controls-container {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    background: var(--bg-card);
                    padding: 16px;
                    border-radius: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                    border: 1px solid var(--border);
                }}
                
                .header-actions {{ display: flex; align-items: center; gap: 16px; }}
                
                .search-input {{
                    padding: 10px 16px;
                    width: 300px;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-family: inherit;
                    font-size: 0.95rem;
                    transition: border-color 0.2s, box-shadow 0.2s;
                }}
                .search-input:focus {{
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
                }}
                
                .stats {{
                    font-size: 0.9rem;
                    color: var(--text-secondary);
                    font-weight: 500;
                }}

                .table-container {{
                    background: var(--bg-card);
                    border-radius: 8px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                    overflow-x: auto;
                    border: 1px solid var(--border);
                }}
                
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    text-align: left; 
                    table-layout: fixed;
                }}
                
                thead {{
                    background-color: #f8fafc;
                    border-bottom: 1px solid var(--border);
                }}
                
                th {{ 
                    padding: 14px 16px; 
                    font-weight: 600; 
                    font-size: 0.8rem; 
                    text-transform: uppercase; 
                    letter-spacing: 0.05em;
                    color: var(--text-secondary);
                    position: sticky;
                    top: 0;
                }}
                
                td {{ 
                    padding: 14px 16px; 
                    border-bottom: 1px solid var(--border);
                    vertical-align: middle;
                    font-size: 0.925rem;
                }}
                
                tr:last-child td {{ border-bottom: none; }}
                tr {{ cursor: pointer; transition: background-color 0.1s; }}
                tr:hover {{ background-color: var(--hover-row); }}
                
                .code-font {{
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.8rem;
                    color: #334155;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    max-width: 0;
                }}

                .method {{ 
                    padding: 4px 10px; 
                    border-radius: 6px; 
                    font-weight: 600; 
                    font-size: 0.75rem; 
                    color: white; 
                    text-transform: uppercase; 
                    letter-spacing: 0.05em;
                    display: inline-block;
                    min-width: 50px;
                    text-align: center;
                }}
                .method.get {{ background-color: #3b82f6; }}
                .method.post {{ background-color: #10b981; }}
                .method.put {{ background-color: #f59e0b; }}
                .method.delete {{ background-color: #ef4444; }}
                .method.patch {{ background-color: #8b5cf6; }}
                
                .badge {{
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    font-weight: 600;
                }}
                .badge-yes {{
                    background-color: #dcfce7;
                    color: #166534;
                }}
                .badge-no {{
                    background-color: #f3f4f6;
                    color: #6b7280;
                }}
                .small-text {{
                    font-size: 0.7rem !important;
                }}
                .center-col {{
                    text-align: center;
                }}
                
                .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
                .back-btn {{ 
                    display: inline-flex; 
                    align-items: center;
                    padding: 8px 16px;
                    background-color: white;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    text-decoration: none; 
                    color: var(--text-main); 
                    font-weight: 500; 
                    font-size: 0.9rem;
                    transition: all 0.2s;
                }}
                .back-btn:hover {{ border-color: var(--primary); color: var(--primary); }}
                
                .detail-container pre {{ 
                    margin: 0; 
                    padding: 24px; 
                    border-radius: 8px; 
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.9rem;
                    line-height: 1.5;
                }}
                
                /* Editor Panel Styles */
                .editor-panel {{
                    background: var(--bg-card);
                    border-radius: 8px;
                    padding: 0;
                    margin-bottom: 24px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                    border: 1px solid var(--border);
                    overflow: hidden;
                }}
                .editor-toggle {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 16px 20px;
                    cursor: pointer;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    transition: background 0.2s;
                }}
                .editor-toggle:hover {{
                    background: linear-gradient(135deg, #5a67d8 0%, #6b46a1 100%);
                }}
                .editor-toggle h3 {{
                    margin: 0;
                    font-size: 1rem;
                    color: white;
                    font-weight: 500;
                }}
                .toggle-icon {{
                    color: white;
                    font-size: 0.8rem;
                }}
                .editor-content {{
                    padding: 20px;
                }}
                .editor-actions {{
                    display: flex;
                    gap: 12px;
                    margin-top: 12px;
                    justify-content: flex-end;
                }}
                .validation-error {{
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    color: #dc2626;
                    padding: 10px 14px;
                    border-radius: 6px;
                    margin-top: 10px;
                    font-size: 0.875rem;
                }}
                .btn-primary {{
                    background: var(--primary);
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.2s;
                }}
                .btn-primary:hover {{ background: var(--primary-hover); }}
                .btn-secondary {{
                    background: white;
                    color: var(--text-main);
                    border: 1px solid var(--border);
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-secondary:hover {{ border-color: var(--primary); color: var(--primary); }}
                
                /* cURL Builder Styles */
                .curl-toggle {{
                    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
                }}
                .curl-toggle:hover {{
                    background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
                }}
                .curl-builder {{
                    padding: 0;
                }}
                .curl-url-row {{
                    display: flex;
                    gap: 8px;
                    margin-bottom: 12px;
                }}
                .curl-method-select {{
                    padding: 12px 16px;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 0.9rem;
                    background: white;
                    cursor: pointer;
                    min-width: 100px;
                }}
                .curl-url-input {{
                    flex: 1;
                    padding: 12px 16px;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.9rem;
                }}
                .curl-url-input:focus {{
                    outline: none;
                    border-color: var(--primary);
                }}
                .btn-send {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-send:hover {{
                    background: linear-gradient(135deg, #059669 0%, #047857 100%);
                    transform: translateY(-1px);
                }}
                .btn-send:disabled {{
                    opacity: 0.7;
                    cursor: not-allowed;
                    transform: none;
                }}
                .curl-base-url {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 16px;
                    font-size: 0.85rem;
                    color: var(--text-secondary);
                }}
                .curl-base-url code {{
                    background: #f1f5f9;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-family: 'JetBrains Mono', monospace;
                }}
                .btn-tiny {{
                    background: transparent;
                    border: 1px solid var(--border);
                    border-radius: 4px;
                    padding: 2px 6px;
                    cursor: pointer;
                    font-size: 0.75rem;
                }}
                .btn-tiny:hover {{
                    background: #f1f5f9;
                }}
                .curl-tabs {{
                    display: flex;
                    border-bottom: 1px solid var(--border);
                    margin-bottom: 16px;
                }}
                .curl-tab {{
                    padding: 10px 20px;
                    background: transparent;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                    color: var(--text-secondary);
                    border-bottom: 2px solid transparent;
                    transition: all 0.2s;
                }}
                .curl-tab:hover {{
                    color: var(--text-main);
                }}
                .curl-tab.active {{
                    color: var(--primary);
                    border-bottom-color: var(--primary);
                }}
                .curl-tab-content {{
                    min-height: 120px;
                }}
                .header-row {{
                    display: flex;
                    gap: 8px;
                    margin-bottom: 8px;
                }}
                .header-key, .header-value {{
                    flex: 1;
                    padding: 10px 12px;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.85rem;
                }}
                .header-key {{
                    max-width: 200px;
                }}
                .btn-remove {{
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    color: #ef4444;
                    border-radius: 6px;
                    padding: 8px 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-remove:hover {{
                    background: #fee2e2;
                }}
                .btn-add-header {{
                    background: transparent;
                    border: 1px dashed var(--border);
                    padding: 10px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    color: var(--text-secondary);
                    width: 100%;
                    margin-top: 8px;
                    transition: all 0.2s;
                }}
                .btn-add-header:hover {{
                    border-color: var(--primary);
                    color: var(--primary);
                    background: rgba(102, 126, 234, 0.05);
                }}
                .curl-body-textarea {{
                    width: 100%;
                    min-height: 150px;
                    padding: 12px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.85rem;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    resize: vertical;
                    background: #1e1e2e;
                    color: #cdd6f4;
                }}
                .curl-command-container {{
                    position: relative;
                }}
                .curl-command {{
                    background: #1e1e2e;
                    color: #a6e3a1;
                    padding: 16px;
                    border-radius: 6px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.85rem;
                    white-space: pre-wrap;
                    word-break: break-all;
                    margin: 0;
                }}
                .btn-copy-curl {{
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    background: rgba(255,255,255,0.1);
                    border: none;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 0.8rem;
                }}
                .btn-copy-curl:hover {{
                    background: rgba(255,255,255,0.2);
                }}
                .curl-response {{
                    margin-top: 20px;
                    border: 1px solid var(--border);
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .response-header {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 12px 16px;
                    background: #f8fafc;
                    border-bottom: 1px solid var(--border);
                }}
                .response-title {{
                    font-weight: 600;
                    color: var(--text-main);
                }}
                .response-status {{
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }}
                .status-ok {{
                    background: #dcfce7;
                    color: #166534;
                }}
                .status-error {{
                    background: #fef2f2;
                    color: #dc2626;
                }}
                .response-time {{
                    font-size: 0.8rem;
                    color: var(--text-secondary);
                    margin-left: auto;
                }}
                .response-body {{
                    background: #1e1e2e;
                    color: #cdd6f4;
                    padding: 16px;
                    margin: 0;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.85rem;
                    white-space: pre-wrap;
                    word-break: break-all;
                    max-height: 300px;
                    overflow-y: auto;
                }}
                .btn-icon {{
                    background: transparent;
                    border: none;
                    cursor: pointer;
                    font-size: 1rem;
                    padding: 4px 8px;
                    border-radius: 4px;
                    transition: background 0.2s;
                }}
                .btn-icon:hover {{ background: rgba(0,0,0,0.05); }}
                .btn-icon.edit {{ color: #2563eb; }}
                .btn-icon.delete {{ color: #ef4444; }}
                .btn-check {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                    font-size: 0.9rem;
                }}
                .btn-check:hover {{ background: linear-gradient(135deg, #059669 0%, #047857 100%); }}
                .btn-check:disabled {{ opacity: 0.7; cursor: not-allowed; }}
                .btn-download {{
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                    font-size: 0.9rem;
                }}
                .btn-download:hover {{ background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {body}
        </body>
        </html>
        """

def run_server(port=8000, config_dir="config"):
    # Allow passing config_dir to the handler
    handler = APIRequestHandler
    
    # Create a custom server class to hold config
    class CustomServer(socketserver.ThreadingTCPServer):
        def __init__(self, *args, **kwargs):
            self.config_dir = config_dir
            super().__init__(*args, **kwargs)

    try:
        with CustomServer(("", port), handler) as httpd:
            print(f"Serving at http://localhost:{port}")
            print(f"Reading config from: {config_dir}")
            
            # Open browser in a separate thread to not block startup
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
                httpd.shutdown()
    except OSError as e:
        print(f"Error starting server on port {port}: {e}")


# --- Host-Grouped Partials Web Server (server-ns) ---

class EnvAPIRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handler for host-grouped partials (develop-saas style)"""
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_env_endpoint_list_html().encode('utf-8'))
            return
        
        # Serve all endpoints view: /endpoints
        if self.path == '/endpoints':
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_all_endpoints_html().encode('utf-8'))
            return
        
        # Serve host detail: /host/<host_file>
        if self.path.startswith('/host/'):
            host_file = self.path.split('/host/')[-1]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_host_detail_html(host_file).encode('utf-8'))
            return
        
        # API: Get endpoints from host file as JSON
        if self.path.startswith('/api/host/'):
            host_file = self.path.split('/api/host/')[-1]
            partial_path = os.path.join(self.server.config_dir, "partials", host_file)
            try:
                with open(partial_path, 'r') as f:
                    content = f.read()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
        
        # API: Get all endpoints as JSON
        if self.path == '/api/endpoints':
            try:
                all_endpoints = self.get_all_endpoints_data()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(all_endpoints).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
        
        super().do_GET()
    
    def get_all_endpoints_data(self):
        """Get all endpoints from all host files"""
        partials_dir = os.path.join(self.server.config_dir, "partials")
        all_endpoints = []
        
        if not os.path.exists(partials_dir):
            return all_endpoints
        
        for filename in sorted(os.listdir(partials_dir)):
            if filename.endswith('.json'):
                partial_path = os.path.join(partials_dir, filename)
                try:
                    with open(partial_path, 'r') as f:
                        endpoints = json.load(f)
                        if isinstance(endpoints, list):
                            for ep in endpoints:
                                ep['_host_file'] = filename
                                all_endpoints.append(ep)
                except:
                    pass
        
        return all_endpoints
    
    def get_all_endpoints_html(self):
        """Generate HTML page showing all endpoints like regular server"""
        all_endpoints = self.get_all_endpoints_data()
        
        rows = ""
        host_index_tracker = {}  # Track local index per host file
        
        for idx, ep in enumerate(all_endpoints):
            host_file = ep.get('_host_file', 'unknown')
            method = ep.get('method', 'GET')
            endpoint = ep.get('endpoint', 'N/A')
            
            # Track local index per host
            if host_file not in host_index_tracker:
                host_index_tracker[host_file] = 0
            local_index = host_index_tracker[host_file]
            host_index_tracker[host_file] += 1
            
            # Get backend info
            backend = ep.get('backend', [])
            if backend and len(backend) > 0:
                hosts = backend[0].get('host', [])
                host = hosts[0] if hosts else 'N/A'
                private_endpoint = backend[0].get('url_pattern', 'N/A')
            else:
                host = 'N/A'
                private_endpoint = 'N/A'
            
            extra_config = bool(ep.get('extra_config'))
            input_headers = ep.get('input_headers', [])
            input_query_strings = ep.get('input_query_strings', [])
            
            extra_config_display = '<span class="badge badge-yes">Yes</span>' if extra_config else '<span class="badge badge-no">No</span>'
            headers_display = ', '.join(input_headers[:3]) + ('...' if len(input_headers) > 3 else '') if input_headers else '-'
            query_display = ', '.join(input_query_strings[:3]) + ('...' if len(input_query_strings) > 3 else '') if input_query_strings else '-'
            
            # Prepare full values for CSV export
            headers_full = ', '.join(input_headers) if input_headers else '-'
            query_full = ', '.join(input_query_strings) if input_query_strings else '-'
            
            # Escape endpoint for data attribute
            endpoint_escaped = endpoint.replace('"', '&quot;')
            
            rows += f"""
            <tr data-host="{host_file}" data-local-index="{local_index}" onclick="viewEndpointDetail('{host_file}', {local_index})" style="cursor: pointer;">
                <td class="code-font small-text">{host_file}</td>
                <td><span class="method {method.lower()}">{method}</span></td>
                <td class="code-font" title="{endpoint}">{endpoint}</td>
                <td class="code-font" title="{private_endpoint}">{private_endpoint}</td>
                <td class="code-font">{host}</td>
                <td class="center-col">{extra_config_display}</td>
                <td class="code-font small-text" title="{headers_display}" data-full="{headers_full}">{headers_display}</td>
                <td class="code-font small-text" title="{query_display}" data-full="{query_full}">{query_display}</td>
                <td class="actions-col" onclick="event.stopPropagation()">
                    <button class="btn-icon edit" onclick="editEndpoint('{host_file}', {local_index})">✎</button>
                    <button class="btn-icon test" onclick="testEndpoint('{endpoint_escaped}', '{method}')">▶</button>
                </td>
            </tr>
            """
        
        return self.get_env_html_template(f"All Endpoints - {self.server.config_dir}", f"""
            <a href="/" class="back-link">← Back to Hosts</a>
            
            <!-- Endpoint Detail/Editor Panel -->
            <div class="editor-panel" id="endpointEditorPanel" style="display: none;">
                <div class="editor-toggle" onclick="toggleEndpointEditor()">
                    <span class="toggle-icon" id="epEditorToggleIcon">▼</span>
                    <h3 id="epEditorTitle">📝 Endpoint Detail</h3>
                    <input type="hidden" id="currentHostFile">
                    <input type="hidden" id="currentEndpointIndex">
                </div>
                <div class="editor-content" id="epEditorContent">
                    <div id="ep-editor-container" style="height: 400px; width: 100%; border: 1px solid var(--border); border-radius: 6px;"></div>
                    <div id="epValidationError" class="validation-error" style="display: none;"></div>
                    <div class="editor-actions">
                        <button class="btn-secondary" onclick="closeEndpointEditor()">Close</button>
                        <button class="btn-primary" onclick="saveEndpointChanges()">💾 Save Changes</button>
                    </div>
                </div>
            </div>
            
            <!-- cURL Web Editor Panel -->
            <div class="editor-panel" id="curlPanel">
                <div class="editor-toggle curl-toggle" onclick="toggleCurlEditor()">
                    <span class="toggle-icon" id="curlToggleIcon">▶</span>
                    <h3>🖥️ cURL Builder & Tester</h3>
                </div>
                <div class="editor-content" id="curlContent" style="display: none;">
                    <div class="curl-builder">
                        <!-- Request URL Row -->
                        <div class="curl-url-row">
                            <select id="curlMethod" class="curl-method-select">
                                <option value="GET">GET</option>
                                <option value="POST">POST</option>
                                <option value="PUT">PUT</option>
                                <option value="DELETE">DELETE</option>
                                <option value="PATCH">PATCH</option>
                            </select>
                            <input type="text" id="curlUrl" class="curl-url-input" placeholder="/api/v1/endpoint" value="/health">
                            <button class="btn-send" onclick="executeCurl()">
                                <span id="sendBtnText">▶ Send</span>
                            </button>
                        </div>
                        
                        <!-- Base URL Info -->
                        <div class="curl-base-url">
                            <span class="base-label">Base URL:</span>
                            <code id="baseUrl">http://localhost:8005</code>
                            <button class="btn-tiny" onclick="editBaseUrl()">✎</button>
                        </div>
                        
                        <!-- Tabs -->
                        <div class="curl-tabs">
                            <button class="curl-tab active" onclick="switchCurlTab('headers')">Headers</button>
                            <button class="curl-tab" onclick="switchCurlTab('body')">Body</button>
                            <button class="curl-tab" onclick="switchCurlTab('curl')">cURL</button>
                        </div>
                        
                        <!-- Headers Tab -->
                        <div class="curl-tab-content" id="tab-headers">
                            <div id="headersContainer">
                                <div class="header-row">
                                    <input type="text" placeholder="Header Name" value="Content-Type" class="header-key">
                                    <input type="text" placeholder="Header Value" value="application/json" class="header-value">
                                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                                </div>
                                <div class="header-row">
                                    <input type="text" placeholder="Header Name" value="Authorization" class="header-key">
                                    <input type="text" placeholder="Header Value" value="Bearer token" class="header-value">
                                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                                </div>
                            </div>
                            <button class="btn-add-header" onclick="addHeader()">+ Add Header</button>
                        </div>
                        
                        <!-- Body Tab -->
                        <div class="curl-tab-content" id="tab-body" style="display: none;">
                            <textarea id="curlBody" class="curl-body-textarea" placeholder='{{"key": "value"}}'></textarea>
                        </div>
                        
                        <!-- cURL Tab -->
                        <div class="curl-tab-content" id="tab-curl" style="display: none;">
                            <div class="curl-command-container">
                                <pre id="curlCommand" class="curl-command">curl -X GET 'http://localhost:8005/health'</pre>
                                <button class="btn-copy-curl" onclick="copyCurlCommand()">📋 Copy</button>
                            </div>
                        </div>
                        
                        <!-- Response Section -->
                        <div class="curl-response" id="curlResponse" style="display: none;">
                            <div class="response-header">
                                <span class="response-title">Response</span>
                                <span class="response-status" id="responseStatus"></span>
                                <span class="response-time" id="responseTime"></span>
                            </div>
                            <pre class="response-body" id="responseBody"></pre>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="controls-container">
                <input type="text" class="search-input" id="searchInput" placeholder="🔍 Search endpoints..." onkeyup="searchTable()">
                <div class="header-actions">
                    <span class="stats">{len(all_endpoints)} endpoints</span>
                    <button class="btn-download" onclick="downloadCSV()">📥 Download CSV</button>
                    <button class="btn-check" onclick="checkConfig()">🔍 Check Config</button>
                </div>
            </div>
            
            <div class="table-wrapper">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th style="min-width: 200px;">Host File</th>
                                <th style="min-width: 80px;">Method</th>
                                <th style="min-width: 250px;">Endpoint</th>
                                <th style="min-width: 200px;">Private Endpoint</th>
                                <th style="min-width: 180px;">Host</th>
                                <th style="min-width: 70px;">Extra</th>
                                <th style="min-width: 150px;">Headers</th>
                                <th style="min-width: 120px;">Query Strings</th>
                                <th style="min-width: 80px;">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="endpointTable">
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <style>
            .table-wrapper {{
                width: 100%;
                margin-bottom: 20px;
            }}
            .table-container {{
                background: var(--surface);
                border-radius: 12px;
                border: 1px solid var(--border);
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }}
            .table-container table {{
                width: 100%;
                min-width: 1250px;
                border-collapse: collapse;
            }}
            .table-container th,
            .table-container td {{
                padding: 12px 16px;
                text-align: left;
                border-bottom: 1px solid var(--border);
                white-space: nowrap;
            }}
            .table-container th {{
                background: #0f172a;
                font-weight: 600;
                color: var(--text-muted);
                font-size: 0.8rem;
                text-transform: uppercase;
                position: sticky;
                top: 0;
            }}
            .table-container tr:hover {{
                background: rgba(59, 130, 246, 0.05);
            }}
            .curl-url-row {{
                display: flex;
                gap: 10px;
                margin-bottom: 12px;
            }}
            .curl-method-select {{
                background: #0f172a;
                border: 1px solid var(--border);
                color: var(--text);
                padding: 10px 14px;
                border-radius: 6px;
                font-weight: 600;
                cursor: pointer;
            }}
            .curl-url-input {{
                flex: 1;
                padding: 10px 14px;
                background: #0f172a;
                border: 1px solid var(--border);
                color: var(--text);
                border-radius: 6px;
                font-family: monospace;
            }}
            .curl-url-input:focus {{ outline: none; border-color: var(--primary); }}
            .btn-send {{
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .btn-send:hover {{ opacity: 0.9; }}
            .btn-send:disabled {{ opacity: 0.6; cursor: not-allowed; }}
            .curl-base-url {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 12px;
                font-size: 0.85rem;
            }}
            .base-label {{ color: var(--text-muted); }}
            .curl-base-url code {{
                background: #0f172a;
                padding: 4px 8px;
                border-radius: 4px;
                color: #60a5fa;
            }}
            .btn-tiny {{
                background: var(--border);
                border: none;
                color: var(--text);
                padding: 4px 8px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8rem;
            }}
            .btn-tiny:hover {{ background: var(--primary); }}
            .curl-tabs {{
                display: flex;
                gap: 4px;
                margin-bottom: 12px;
            }}
            .curl-tab {{
                background: var(--border);
                border: none;
                color: var(--text-muted);
                padding: 8px 16px;
                border-radius: 6px 6px 0 0;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .curl-tab:hover {{ background: #475569; }}
            .curl-tab.active {{
                background: #0f172a;
                color: var(--text);
            }}
            .curl-tab-content {{
                background: #0f172a;
                border-radius: 0 6px 6px 6px;
                padding: 16px;
                min-height: 120px;
            }}
            .header-row {{
                display: flex;
                gap: 8px;
                margin-bottom: 8px;
            }}
            .header-key, .header-value {{
                flex: 1;
                padding: 8px 12px;
                background: var(--surface);
                border: 1px solid var(--border);
                color: var(--text);
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.85rem;
            }}
            .header-key:focus, .header-value:focus {{ outline: none; border-color: var(--primary); }}
            .btn-remove {{
                background: var(--error);
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                cursor: pointer;
            }}
            .btn-remove:hover {{ opacity: 0.8; }}
            .btn-add-header {{
                background: var(--border);
                color: var(--text);
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                margin-top: 8px;
            }}
            .btn-add-header:hover {{ background: var(--primary); }}
            .curl-body-textarea {{
                width: 100%;
                height: 120px;
                background: var(--surface);
                border: 1px solid var(--border);
                color: var(--text);
                border-radius: 4px;
                padding: 12px;
                font-family: monospace;
                font-size: 0.85rem;
                resize: vertical;
            }}
            .curl-body-textarea:focus {{ outline: none; border-color: var(--primary); }}
            .curl-command-container {{
                position: relative;
            }}
            .curl-command {{
                background: var(--surface);
                padding: 12px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.85rem;
                white-space: pre-wrap;
                word-break: break-all;
                margin: 0;
            }}
            .btn-copy-curl {{
                position: absolute;
                top: 8px;
                right: 8px;
                background: var(--primary);
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8rem;
            }}
            .btn-copy-curl:hover {{ opacity: 0.8; }}
            .curl-response {{
                margin-top: 16px;
                background: var(--surface);
                border-radius: 8px;
                overflow: hidden;
            }}
            .response-header {{
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 14px;
                background: #0f172a;
                border-bottom: 1px solid var(--border);
            }}
            .response-title {{ font-weight: 600; }}
            .response-status {{
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.8rem;
                font-weight: 600;
            }}
            .status-ok {{ background: var(--success); color: white; }}
            .status-error {{ background: var(--error); color: white; }}
            .response-time {{ color: var(--text-muted); font-size: 0.85rem; }}
            .response-body {{
                padding: 12px;
                margin: 0;
                font-family: monospace;
                font-size: 0.85rem;
                white-space: pre-wrap;
                max-height: 300px;
                overflow: auto;
            }}
            .btn-download {{
                background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                cursor: pointer;
            }}
            .btn-download:hover {{ opacity: 0.9; }}
            .btn-icon {{
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
                font-size: 0.8rem;
                cursor: pointer;
                transition: all 0.2s;
                margin: 0 2px;
            }}
            .btn-icon.edit {{
                background: #3b82f6;
                color: white;
            }}
            .btn-icon.edit:hover {{ background: #2563eb; }}
            .btn-icon.test {{
                background: #10b981;
                color: white;
            }}
            .btn-icon.test:hover {{ background: #059669; }}
            </style>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.7/ace.min.js"></script>
            <script>
            let endpointsData = [];
            let epEditor = null;
            let epEditorInitialized = false;
            
            // Load all endpoints data
            async function loadEndpointsData() {{
                try {{
                    const response = await fetch('/api/endpoints');
                    endpointsData = await response.json();
                }} catch (e) {{
                    console.error('Failed to load endpoints:', e);
                }}
            }}
            loadEndpointsData();
            
            function searchTable() {{
                const filter = document.getElementById("searchInput").value.toUpperCase();
                const rows = document.querySelectorAll("#endpointTable tr");
                rows.forEach(row => {{
                    const text = row.textContent.toUpperCase();
                    row.style.display = text.includes(filter) ? "" : "none";
                }});
            }}
            
            function initEpEditor() {{
                if (epEditorInitialized) return;
                epEditor = ace.edit("ep-editor-container");
                epEditor.setTheme("ace/theme/monokai");
                epEditor.session.setMode("ace/mode/json");
                epEditor.setOptions({{
                    fontSize: "13px",
                    showPrintMargin: false,
                }});
                epEditor.session.on('change', validateEpJson);
                epEditorInitialized = true;
            }}
            
            function validateEpJson() {{
                const content = epEditor.getValue();
                const errorDiv = document.getElementById("epValidationError");
                try {{
                    JSON.parse(content);
                    errorDiv.style.display = "none";
                    return true;
                }} catch (e) {{
                    errorDiv.textContent = "⚠️ JSON Error: " + e.message;
                    errorDiv.style.display = "block";
                    return false;
                }}
            }}
            
            async function viewEndpointDetail(hostFile, localIndex) {{
                // Show editor panel
                document.getElementById("endpointEditorPanel").style.display = "block";
                document.getElementById("epEditorTitle").textContent = "📝 Endpoint - " + hostFile + " [" + localIndex + "]";
                document.getElementById("currentHostFile").value = hostFile;
                document.getElementById("currentEndpointIndex").value = localIndex;
                
                initEpEditor();
                
                // Load endpoint data from host file
                try {{
                    const response = await fetch('/api/host/' + hostFile);
                    const endpoints = await response.json();
                    
                    if (endpoints[localIndex]) {{
                        epEditor.setValue(JSON.stringify(endpoints[localIndex], null, 2), -1);
                    }} else {{
                        epEditor.setValue("{{}}", -1);
                    }}
                    
                    // Scroll to panel
                    document.getElementById("endpointEditorPanel").scrollIntoView({{ behavior: 'smooth' }});
                }} catch (e) {{
                    alert("Failed to load endpoint: " + e.message);
                }}
            }}
            
            function editEndpoint(hostFile, index) {{
                viewEndpointDetail(hostFile, index);
            }}
            
            function testEndpoint(endpoint, method) {{
                // Open cURL panel and set endpoint
                const content = document.getElementById("curlContent");
                const icon = document.getElementById("curlToggleIcon");
                content.style.display = "block";
                icon.textContent = "▼";
                
                document.getElementById("curlUrl").value = endpoint;
                document.getElementById("curlMethod").value = method;
                updateCurlCommand();
                
                // Scroll to curl panel
                document.getElementById("curlPanel").scrollIntoView({{ behavior: 'smooth' }});
            }}
            
            function toggleEndpointEditor() {{
                const content = document.getElementById("epEditorContent");
                const icon = document.getElementById("epEditorToggleIcon");
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "▼";
                    if (epEditor) epEditor.resize();
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "▶";
                }}
            }}
            
            function closeEndpointEditor() {{
                document.getElementById("endpointEditorPanel").style.display = "none";
            }}
            
            async function saveEndpointChanges() {{
                if (!validateEpJson()) {{
                    alert("Please fix the JSON errors before saving.");
                    return;
                }}
                
                const hostFile = document.getElementById("currentHostFile").value;
                const index = parseInt(document.getElementById("currentEndpointIndex").value);
                const content = epEditor.getValue();
                const endpointData = JSON.parse(content);
                
                try {{
                    const response = await fetch("/api/env/update", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{
                            host_file: hostFile,
                            index: index,
                            endpoint: endpointData
                        }})
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        alert("✅ Endpoint saved successfully!");
                        location.reload();
                    }} else {{
                        alert("❌ Error: " + result.error);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }}
            }}
            
            function selectEndpoint(endpoint, method) {{
                // Open cURL panel and set endpoint
                const content = document.getElementById("curlContent");
                const icon = document.getElementById("curlToggleIcon");
                content.style.display = "block";
                icon.textContent = "▼";
                
                document.getElementById("curlUrl").value = endpoint;
                document.getElementById("curlMethod").value = method;
                updateCurlCommand();
                
                // Scroll to curl panel
                document.getElementById("curlPanel").scrollIntoView({{ behavior: 'smooth' }});
            }}
            
            // cURL Builder functions
            let baseUrl = "http://localhost:8005";
            
            function toggleCurlEditor() {{
                const content = document.getElementById("curlContent");
                const icon = document.getElementById("curlToggleIcon");
                
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "▼";
                    updateCurlCommand();
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "▶";
                }}
            }}
            
            function switchCurlTab(tabName) {{
                document.querySelectorAll('.curl-tab').forEach(t => t.classList.remove('active'));
                event.target.classList.add('active');
                document.querySelectorAll('.curl-tab-content').forEach(c => c.style.display = 'none');
                document.getElementById('tab-' + tabName).style.display = 'block';
                if (tabName === 'curl') updateCurlCommand();
            }}
            
            function addHeader() {{
                const container = document.getElementById('headersContainer');
                const row = document.createElement('div');
                row.className = 'header-row';
                row.innerHTML = `
                    <input type="text" placeholder="Header Name" class="header-key">
                    <input type="text" placeholder="Header Value" class="header-value">
                    <button class="btn-remove" onclick="removeHeader(this)">✕</button>
                `;
                container.appendChild(row);
            }}
            
            function removeHeader(btn) {{ btn.parentElement.remove(); }}
            
            function editBaseUrl() {{
                const newUrl = prompt("Enter base URL:", baseUrl);
                if (newUrl) {{
                    baseUrl = newUrl;
                    document.getElementById('baseUrl').textContent = baseUrl;
                    updateCurlCommand();
                }}
            }}
            
            function getHeaders() {{
                const headers = {{}};
                document.querySelectorAll('.header-row').forEach(row => {{
                    const key = row.querySelector('.header-key').value.trim();
                    const value = row.querySelector('.header-value').value.trim();
                    if (key) headers[key] = value;
                }});
                return headers;
            }}
            
            function updateCurlCommand() {{
                const method = document.getElementById('curlMethod').value;
                const url = document.getElementById('curlUrl').value;
                const body = document.getElementById('curlBody').value;
                const headers = getHeaders();
                
                let cmd = `curl -X ${{method}} '${{baseUrl}}${{url}}'`;
                Object.keys(headers).forEach(key => {{
                    cmd += ` \\\\\\n  -H '${{key}}: ${{headers[key]}}'`;
                }});
                if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {{
                    cmd += ` \\\\\\n  -d '${{body}}'`;
                }}
                document.getElementById('curlCommand').textContent = cmd;
            }}
            
            function copyCurlCommand() {{
                const cmd = document.getElementById('curlCommand').textContent;
                navigator.clipboard.writeText(cmd);
                alert("cURL command copied!");
            }}
            
            async function executeCurl() {{
                const btn = document.querySelector('.btn-send');
                const btnText = document.getElementById('sendBtnText');
                const method = document.getElementById('curlMethod').value;
                const urlPath = document.getElementById('curlUrl').value;
                const body = document.getElementById('curlBody').value;
                const headers = getHeaders();
                
                btn.disabled = true;
                btnText.textContent = "⏳ Sending...";
                const startTime = performance.now();
                
                try {{
                    const fetchOptions = {{ method: method, headers: headers }};
                    if (body && ['POST', 'PUT', 'PATCH'].includes(method)) fetchOptions.body = body;
                    
                    const response = await fetch(baseUrl + urlPath, fetchOptions);
                    const endTime = performance.now();
                    const duration = Math.round(endTime - startTime);
                    
                    let responseText;
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {{
                        const json = await response.json();
                        responseText = JSON.stringify(json, null, 2);
                    }} else {{
                        responseText = await response.text();
                    }}
                    
                    document.getElementById('curlResponse').style.display = 'block';
                    document.getElementById('responseStatus').textContent = response.status + ' ' + response.statusText;
                    document.getElementById('responseStatus').className = 'response-status ' + (response.ok ? 'status-ok' : 'status-error');
                    document.getElementById('responseTime').textContent = duration + 'ms';
                    document.getElementById('responseBody').textContent = responseText;
                }} catch (e) {{
                    document.getElementById('curlResponse').style.display = 'block';
                    document.getElementById('responseStatus').textContent = 'Error';
                    document.getElementById('responseStatus').className = 'response-status status-error';
                    document.getElementById('responseTime').textContent = '';
                    document.getElementById('responseBody').textContent = e.message;
                }} finally {{
                    btn.disabled = false;
                    btnText.textContent = "▶ Send";
                }}
            }}
            
            function downloadCSV() {{
                const table = document.querySelector("table");
                const rows = table.querySelectorAll("tr");
                let csv = [];
                
                const headers = ["Host File", "Method", "Endpoint", "Private Endpoint", "Host", "Extra Config", "Headers", "Query Strings"];
                csv.push(headers.join("|"));
                
                const tbody = document.getElementById("endpointTable");
                const dataRows = tbody.querySelectorAll("tr");
                
                dataRows.forEach(row => {{
                    if (row.style.display === "none") return;
                    const cells = row.querySelectorAll("td");
                    if (cells.length >= 8) {{
                        const rowData = [
                            cells[0].textContent.trim(),
                            cells[1].textContent.trim(),
                            cells[2].textContent.trim(),
                            cells[3].textContent.trim(),
                            cells[4].textContent.trim(),
                            cells[5].textContent.trim(),
                            cells[6].getAttribute('data-full') || cells[6].textContent.trim(),
                            cells[7].getAttribute('data-full') || cells[7].textContent.trim()
                        ];
                        csv.push(rowData.join("|"));
                    }}
                }});
                
                const csvContent = csv.join("\\n");
                const blob = new Blob([csvContent], {{ type: "text/csv;charset=utf-8;" }});
                const link = document.createElement("a");
                const url = URL.createObjectURL(blob);
                link.setAttribute("href", url);
                link.setAttribute("download", "endpoints_" + new Date().toISOString().slice(0,10) + ".csv");
                link.style.visibility = "hidden";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}
            
            async function checkConfig() {{
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = "⏳ Checking...";
                
                try {{
                    const response = await fetch("/api/check", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }}
                    }});
                    
                    const result = await response.json();
                    
                    let message = "";
                    if (result.results) {{
                        for (const r of result.results) {{
                            const status = r.success ? "✅" : "❌";
                            message += status + " " + r.step + "\\n";
                            if (r.output) message += r.output + "\\n";
                            if (r.error && !r.success) message += "Error: " + r.error + "\\n";
                        }}
                    }}
                    
                    if (result.success) {{
                        alert("✅ All checks passed!\\n\\n" + message);
                    }} else {{
                        alert("❌ Some checks failed:\\n\\n" + message);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }} finally {{
                    btn.disabled = false;
                    btn.textContent = "🔍 Check Config";
                }}
            }}
            
            // Update curl command on input change
            document.addEventListener('DOMContentLoaded', function() {{
                const curlMethod = document.getElementById('curlMethod');
                const curlUrl = document.getElementById('curlUrl');
                const curlBody = document.getElementById('curlBody');
                
                if (curlMethod) curlMethod.addEventListener('change', updateCurlCommand);
                if (curlUrl) curlUrl.addEventListener('input', updateCurlCommand);
                if (curlBody) curlBody.addEventListener('input', updateCurlCommand);
                document.getElementById('headersContainer')?.addEventListener('input', updateCurlCommand);
            }});
            </script>
        """)
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        # Handle check API for env template
        if self.path == '/api/check':
            try:
                template = f"{os.path.basename(self.server.config_dir)}.tmpl"
                results = check_krakend(config_dir=self.server.config_dir, template=template)
                all_success = all(r["success"] for r in results)
                response = {"success": all_success, "results": results}
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        
        # Handle create endpoint in host file
        if self.path == '/api/env/create':
            try:
                data = json.loads(post_data)
                host_file = data.get('host_file')
                endpoint_data = data.get('endpoint')
                
                partial_path = os.path.join(self.server.config_dir, "partials", host_file)
                
                # Load existing endpoints
                with open(partial_path, 'r') as f:
                    endpoints = json.load(f)
                
                # Append new endpoint
                endpoints.append(endpoint_data)
                
                # Save back
                with open(partial_path, 'w') as f:
                    json.dump(endpoints, f, indent=2)
                
                response = {"success": True, "message": f"Endpoint added to {host_file}"}
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        
        # Handle update endpoint in host file
        if self.path == '/api/env/update':
            try:
                data = json.loads(post_data)
                host_file = data.get('host_file')
                endpoint_index = data.get('index')
                endpoint_data = data.get('endpoint')
                
                partial_path = os.path.join(self.server.config_dir, "partials", host_file)
                
                # Load existing endpoints
                with open(partial_path, 'r') as f:
                    endpoints = json.load(f)
                
                # Update endpoint at index
                if 0 <= endpoint_index < len(endpoints):
                    endpoints[endpoint_index] = endpoint_data
                else:
                    raise ValueError(f"Invalid index: {endpoint_index}")
                
                # Save back
                with open(partial_path, 'w') as f:
                    json.dump(endpoints, f, indent=2)
                
                response = {"success": True, "message": f"Endpoint updated in {host_file}"}
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        
        # Handle delete endpoint from host file
        if self.path == '/api/env/delete':
            try:
                data = json.loads(post_data)
                host_file = data.get('host_file')
                endpoint_index = data.get('index')
                
                partial_path = os.path.join(self.server.config_dir, "partials", host_file)
                
                # Load existing endpoints
                with open(partial_path, 'r') as f:
                    endpoints = json.load(f)
                
                # Delete endpoint at index
                if 0 <= endpoint_index < len(endpoints):
                    del endpoints[endpoint_index]
                else:
                    raise ValueError(f"Invalid index: {endpoint_index}")
                
                # Save back
                with open(partial_path, 'w') as f:
                    json.dump(endpoints, f, indent=2)
                
                response = {"success": True, "message": f"Endpoint deleted from {host_file}"}
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        
        # Handle add new host
        if self.path == '/api/env/add-host':
            try:
                data = json.loads(post_data)
                host_name = data.get('host_name', '').strip()
                
                if not host_name or ':' not in host_name:
                    raise ValueError("Invalid host name format. Use: service-name:port")
                
                # Create filename from host name (replace : with -)
                host_file = host_name.replace(':', '-') + '.json'
                partial_path = os.path.join(self.server.config_dir, "partials", host_file)
                
                # Check if already exists
                if os.path.exists(partial_path):
                    raise ValueError(f"Host file {host_file} already exists")
                
                # Create empty array file
                with open(partial_path, 'w') as f:
                    json.dump([], f, indent=2)
                
                # Add to endpoint.json mapping
                endpoint_file = os.path.join(self.server.config_dir, "settings/endpoint.json")
                with open(endpoint_file, 'r') as f:
                    endpoint_data = json.load(f)
                
                endpoint_data['mapping_group'].append({"id": host_file})
                
                with open(endpoint_file, 'w') as f:
                    json.dump(endpoint_data, f, indent=2)
                
                response = {"success": True, "message": f"Host {host_file} created", "file": host_file}
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return
        
        super().do_POST()

    
    def get_env_endpoint_list_html(self):
        """Generate HTML listing all hosts and their endpoint counts"""
        endpoint_file = os.path.join(self.server.config_dir, "settings/endpoint.json")
        partials_dir = os.path.join(self.server.config_dir, "partials")
        
        try:
            with open(endpoint_file, 'r') as f:
                data = json.load(f)
                mapping_group = data.get("mapping_group", [])
        except Exception as e:
            return f"<h1>Error loading endpoints</h1><p>{e}</p>"
        
        # Load each host file to count endpoints and get method counts
        host_data = []
        total_endpoints = 0
        for item in mapping_group:
            host_file = item.get('id', '')
            host_name = host_file.replace('.json', '')
            host_path = os.path.join(partials_dir, host_file)
            
            endpoints = []
            if os.path.exists(host_path):
                try:
                    with open(host_path, 'r') as f:
                        endpoints = json.load(f)
                except:
                    pass
            
            # Count methods
            method_counts = {}
            for ep in endpoints:
                method = ep.get('method') or 'GET'
                method_counts[method] = method_counts.get(method, 0) + 1
            
            endpoint_count = len(endpoints) if isinstance(endpoints, list) else 0
            total_endpoints += endpoint_count
            host_data.append({
                "file": host_file,
                "name": host_name,
                "count": endpoint_count,
                "methods": method_counts
            })
        
        # Build table rows HTML
        rows = ""
        for idx, host in enumerate(host_data):
            # Build method badges
            method_badges = ""
            for method, count in sorted(host['methods'].items()):
                method_badges += f'<span class="method-badge {method.lower()}">{method} ({count})</span>'
            
            rows += f"""
            <tr onclick="window.location='/host/{host['file']}'" style="cursor: pointer;">
                <td>{idx + 1}</td>
                <td class="code-font"><strong>{host['name']}</strong></td>
                <td class="center-col"><span class="count-badge">{host['count']}</span></td>
                <td>{method_badges or '-'}</td>
                <td class="actions-col" onclick="event.stopPropagation()">
                    <a href="/host/{host['file']}" class="btn-view">View</a>
                </td>
            </tr>
            """
        
        return self.get_env_html_template("API Gateway - Host Groups", f"""
            <!-- Add Host Panel -->
            <div class="editor-panel" id="addHostPanel">
                <div class="editor-toggle" onclick="toggleAddHost()">
                    <span class="toggle-icon" id="addHostToggleIcon">+</span>
                    <h3>Add New Host</h3>
                </div>
                <div class="editor-content" id="addHostContent" style="display: none;">
                    <div class="form-group">
                        <label>Host Name (e.g. saas-be-new-service:9999)</label>
                        <input type="text" id="newHostName" class="form-input" placeholder="service-name:port">
                    </div>
                    <div id="addHostError" class="validation-error" style="display: none;"></div>
                    <div class="editor-actions">
                        <button class="btn-primary" onclick="createHost()">Create Host</button>
                    </div>
                </div>
            </div>
            
            <div class="controls-container">
                <input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Search hosts..." class="search-input">
                <div class="header-actions">
                    <span class="stats">{len(mapping_group)} Hosts | {total_endpoints} Endpoints</span>
                    <a href="/endpoints" class="btn-check" style="text-decoration: none;">📋 View All Endpoints</a>
                    <button class="btn-check" onclick="checkConfig()">Check Config</button>
                </div>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th style="width: 35%;">Host / Service</th>
                            <th style="width: 100px;">Endpoints</th>
                            <th>Methods</th>
                            <th style="width: 80px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="hostTable">
                        {rows}
                    </tbody>
                </table>
            </div>
            
            <script>
            function searchTable() {{
                const filter = document.getElementById("searchInput").value.toUpperCase();
                const rows = document.querySelectorAll("#hostTable tr");
                rows.forEach(row => {{
                    const text = row.textContent.toUpperCase();
                    row.style.display = text.includes(filter) ? "" : "none";
                }});
            }}
            
            function toggleAddHost() {{
                const content = document.getElementById("addHostContent");
                const icon = document.getElementById("addHostToggleIcon");
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "-";
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "+";
                }}
            }}
            
            async function createHost() {{
                const hostName = document.getElementById("newHostName").value.trim();
                const errorDiv = document.getElementById("addHostError");
                
                if (!hostName) {{
                    errorDiv.textContent = "Please enter a host name";
                    errorDiv.style.display = "block";
                    return;
                }}
                
                // Validate format (should contain colon and port)
                if (!hostName.includes(':')) {{
                    errorDiv.textContent = "Invalid format. Use: service-name:port";
                    errorDiv.style.display = "block";
                    return;
                }}
                
                try {{
                    const response = await fetch("/api/env/add-host", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ host_name: hostName }})
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        location.reload();
                    }} else {{
                        errorDiv.textContent = "Error: " + result.error;
                        errorDiv.style.display = "block";
                    }}
                }} catch (e) {{
                    errorDiv.textContent = "Network error: " + e;
                    errorDiv.style.display = "block";
                }}
            }}
            
            async function checkConfig() {{
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = "Checking...";
                try {{
                    const response = await fetch("/api/check", {{ method: "POST" }});
                    const result = await response.json();
                    let message = "";
                    if (result.results) {{
                        for (const r of result.results) {{
                            message += (r.success ? "[OK] " : "[FAIL] ") + r.step + "\\n";
                            if (r.output) message += r.output + "\\n";
                        }}
                    }}
                    alert(result.success ? "All checks passed!\\n\\n" + message : "Checks failed:\\n\\n" + message);
                }} catch (e) {{
                    alert("Network error: " + e);
                }} finally {{
                    btn.disabled = false;
                    btn.textContent = "Check Config";
                }}
            }}
            </script>
        """)


    
    def get_host_detail_html(self, host_file):
        """Generate HTML showing all endpoints in a host file"""
        partial_path = os.path.join(self.server.config_dir, "partials", host_file)
        host_name = host_file.replace('.json', '')
        
        try:
            with open(partial_path, 'r') as f:
                endpoints = json.load(f)
        except Exception as e:
            return f"<h1>Error loading {host_file}</h1><p>{e}</p>"
        
        rows = ""
        for idx, ep in enumerate(endpoints):
            method = ep.get('method') or 'GET'
            endpoint = ep.get('endpoint', 'N/A')
            backend = ep.get('backend', [{}])[0] if ep.get('backend') else {}
            url_pattern = backend.get('url_pattern', 'N/A')
            extra_config = bool(ep.get('extra_config'))
            input_headers = ', '.join(ep.get('input_headers', [])) or '-'
            
            extra_badge = '<span class="badge badge-yes">Yes</span>' if extra_config else '<span class="badge badge-no">No</span>'
            
            rows += f"""
            <tr>
                <td>{idx + 1}</td>
                <td><span class="method {method.lower()}">{method}</span></td>
                <td class="code-font">{endpoint}</td>
                <td class="code-font">{url_pattern}</td>
                <td class="center-col">{extra_badge}</td>
                <td class="code-font small-text">{input_headers}</td>
                <td class="actions-col">
                    <button class="btn-icon edit" onclick="loadEndpointForEdit({idx})">Edit</button>
                    <button class="btn-icon delete" onclick="deleteEndpoint({idx})">Del</button>
                </td>
            </tr>
            """
        
        # Get host for default template - replace only the last hyphen (before port) with colon
        # e.g. saas-be-admin-manager-9510 -> saas-be-admin-manager:9510
        parts = host_name.rsplit('-', 1)
        host_for_template = ':'.join(parts) if len(parts) == 2 else host_name
        
        default_template = json.dumps({
            "endpoint": "/api/v1/new-endpoint",
            "method": "GET",
            "output_encoding": "no-op",
            "input_headers": ["Authorization", "Content-Type"],
            "backend": [{
                "url_pattern": "/internal/endpoint",
                "encoding": "no-op",
                "sd": "static",
                "host": [host_for_template],
                "disable_host_sanitize": False
            }]
        }, indent=2)
        
        return self.get_env_html_template(f"Host: {host_name}", f"""
            <a href="/" class="back-link">Back to Host List</a>
            
            <!-- Editor Panel -->
            <div class="editor-panel" id="editorPanel">
                <div class="editor-toggle" onclick="toggleEditor()">
                    <span class="toggle-icon" id="toggleIcon">+</span>
                    <h3 id="editorTitle">Create New Endpoint</h3>
                    <input type="hidden" id="editIndex" value="">
                </div>
                <div class="editor-content" id="editorContent" style="display: none;">
                    <textarea id="editorTextarea" class="editor-textarea" rows="15">{default_template}</textarea>
                    <div id="validationError" class="validation-error" style="display: none;"></div>
                    <div class="editor-actions">
                        <button class="btn-secondary" onclick="resetEditor()">Reset</button>
                        <button class="btn-primary" onclick="saveEndpoint()">Save</button>
                    </div>
                </div>
            </div>
            
            <div class="controls-container">
                <input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Search endpoints..." class="search-input">
                <span class="stats">{len(endpoints)} Endpoints</span>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 40px;">#</th>
                            <th style="width: 70px;">Method</th>
                            <th style="width: 25%;">Endpoint</th>
                            <th style="width: 25%;">URL Pattern</th>
                            <th style="width: 60px;">Extra</th>
                            <th>Headers</th>
                            <th style="width: 100px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="endpointTable">
                        {rows}
                    </tbody>
                </table>
            </div>
            
            <script>
            const hostFile = "{host_file}";
            let isEditMode = false;
            let endpoints = {json.dumps(endpoints)};
            
            const defaultTemplate = {default_template};
            
            function toggleEditor() {{
                const content = document.getElementById("editorContent");
                const icon = document.getElementById("toggleIcon");
                if (content.style.display === "none") {{
                    content.style.display = "block";
                    icon.textContent = "-";
                }} else {{
                    content.style.display = "none";
                    icon.textContent = "+";
                }}
            }}
            
            function validateJson() {{
                const content = document.getElementById("editorTextarea").value;
                const errorDiv = document.getElementById("validationError");
                try {{
                    JSON.parse(content);
                    errorDiv.style.display = "none";
                    return true;
                }} catch (e) {{
                    errorDiv.textContent = "JSON Error: " + e.message;
                    errorDiv.style.display = "block";
                    return false;
                }}
            }}
            
            function resetEditor() {{
                isEditMode = false;
                document.getElementById("editorTitle").innerText = "Create New Endpoint";
                document.getElementById("editIndex").value = "";
                document.getElementById("editorTextarea").value = JSON.stringify(defaultTemplate, null, 2);
                document.getElementById("validationError").style.display = "none";
            }}
            
            function loadEndpointForEdit(index) {{
                const content = document.getElementById("editorContent");
                const icon = document.getElementById("toggleIcon");
                content.style.display = "block";
                icon.textContent = "-";
                
                isEditMode = true;
                document.getElementById("editorTitle").innerText = "Edit Endpoint #" + (index + 1);
                document.getElementById("editIndex").value = index;
                document.getElementById("editorTextarea").value = JSON.stringify(endpoints[index], null, 2);
                
                document.getElementById("editorPanel").scrollIntoView({{ behavior: 'smooth' }});
            }}
            
            async function saveEndpoint() {{
                if (!validateJson()) {{
                    alert("Please fix the JSON errors before saving.");
                    return;
                }}
                
                const index = document.getElementById("editIndex").value;
                const content = document.getElementById("editorTextarea").value;
                const endpointData = JSON.parse(content);
                
                const url = isEditMode ? "/api/env/update" : "/api/env/create";
                const body = isEditMode 
                    ? {{ host_file: hostFile, index: parseInt(index), endpoint: endpointData }}
                    : {{ host_file: hostFile, endpoint: endpointData }};
                
                try {{
                    const response = await fetch(url, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify(body)
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        location.reload();
                    }} else {{
                        alert("Error: " + result.error);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }}
            }}
            
            async function deleteEndpoint(index) {{
                if (!confirm("Are you sure you want to delete endpoint #" + (index + 1) + "?")) return;
                
                try {{
                    const response = await fetch("/api/env/delete", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ host_file: hostFile, index: index }})
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        location.reload();
                    }} else {{
                        alert("Error: " + result.error);
                    }}
                }} catch (e) {{
                    alert("Network error: " + e);
                }}
            }}
            
            function searchTable() {{
                const filter = document.getElementById("searchInput").value.toUpperCase();
                const rows = document.querySelectorAll("#endpointTable tr");
                rows.forEach(row => {{
                    const text = row.textContent.toUpperCase();
                    row.style.display = text.includes(filter) ? "" : "none";
                }});
            }}
            </script>
        """)

    
    def get_env_html_template(self, title, body):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                :root {{
                    --bg: #0f172a;
                    --surface: #1e293b;
                    --border: #334155;
                    --text: #f1f5f9;
                    --text-muted: #94a3b8;
                    --primary: #3b82f6;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --error: #ef4444;
                }}
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: var(--bg);
                    color: var(--text);
                    padding: 24px;
                    min-height: 100vh;
                }}
                h1 {{
                    font-size: 1.75rem;
                    margin-bottom: 20px;
                    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                .controls-container {{
                    display: flex;
                    gap: 16px;
                    margin-bottom: 20px;
                    align-items: center;
                    flex-wrap: wrap;
                }}
                .search-input {{
                    flex: 1;
                    min-width: 250px;
                    padding: 10px 14px;
                    border: 1px solid var(--border);
                    background: var(--surface);
                    color: var(--text);
                    border-radius: 8px;
                    font-size: 0.95rem;
                }}
                .search-input:focus {{ outline: none; border-color: var(--primary); }}
                .header-actions {{ display: flex; gap: 12px; align-items: center; }}
                .stats {{ color: var(--text-muted); font-size: 0.9rem; }}
                .host-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                    gap: 16px;
                }}
                .host-card {{
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    padding: 20px;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .host-card:hover {{
                    border-color: var(--primary);
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
                }}
                .host-name {{
                    font-weight: 600;
                    font-size: 1rem;
                    color: var(--text);
                    margin-bottom: 8px;
                    word-break: break-all;
                }}
                .host-count {{
                    color: var(--text-muted);
                    font-size: 0.85rem;
                }}
                .back-link {{
                    color: var(--primary);
                    text-decoration: none;
                    display: inline-block;
                    margin-bottom: 16px;
                }}
                .back-link:hover {{ text-decoration: underline; }}
                .table-container {{
                    background: var(--surface);
                    border-radius: 12px;
                    overflow: hidden;
                    border: 1px solid var(--border);
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{
                    padding: 12px 16px;
                    text-align: left;
                    border-bottom: 1px solid var(--border);
                }}
                th {{
                    background: #0f172a;
                    font-weight: 600;
                    color: var(--text-muted);
                    font-size: 0.8rem;
                    text-transform: uppercase;
                }}
                tr:hover {{ background: rgba(59, 130, 246, 0.05); }}
                .code-font {{ font-family: monospace; font-size: 0.85rem; }}
                .small-text {{ font-size: 0.75rem; color: var(--text-muted); }}
                .center-col {{ text-align: center; }}
                .method {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }}
                .method.get {{ background: #0d9488; color: white; }}
                .method.post {{ background: #2563eb; color: white; }}
                .method.put {{ background: #d97706; color: white; }}
                .method.delete {{ background: #dc2626; color: white; }}
                .method.patch {{ background: #7c3aed; color: white; }}
                .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; }}
                .badge-yes {{ background: #10b981; color: white; }}
                .badge-no {{ background: var(--border); color: var(--text-muted); }}
                .btn-check {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                }}
                .btn-check:hover {{ opacity: 0.9; }}
                .btn-check:disabled {{ opacity: 0.6; cursor: not-allowed; }}
                .method-badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    font-weight: 600;
                    margin-right: 4px;
                    margin-bottom: 2px;
                }}
                .method-badge.get {{ background: #0d9488; color: white; }}
                .method-badge.post {{ background: #2563eb; color: white; }}
                .method-badge.put {{ background: #d97706; color: white; }}
                .method-badge.delete {{ background: #dc2626; color: white; }}
                .method-badge.patch {{ background: #7c3aed; color: white; }}
                .count-badge {{
                    display: inline-block;
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    color: white;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 0.85rem;
                }}
                .btn-view {{
                    display: inline-block;
                    padding: 4px 10px;
                    background: var(--primary);
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    transition: all 0.2s;
                }}
                .btn-view:hover {{ background: #2563eb; }}
                .actions-col {{ text-align: center; }}
                /* Editor Panel Styles */
                .editor-panel {{
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    margin-bottom: 20px;
                    overflow: hidden;
                }}
                .editor-toggle {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 16px 20px;
                    cursor: pointer;
                    transition: background 0.2s;
                }}
                .editor-toggle:hover {{ background: rgba(59, 130, 246, 0.05); }}
                .editor-toggle h3 {{ font-size: 1rem; font-weight: 600; }}
                .toggle-icon {{
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: var(--primary);
                    color: white;
                    border-radius: 4px;
                    font-weight: 600;
                }}
                .editor-content {{
                    padding: 0 20px 20px;
                }}
                .editor-textarea {{
                    width: 100%;
                    padding: 12px;
                    background: #0f172a;
                    border: 1px solid var(--border);
                    border-radius: 8px;
                    color: var(--text);
                    font-family: monospace;
                    font-size: 0.85rem;
                    resize: vertical;
                }}
                .editor-textarea:focus {{ outline: none; border-color: var(--primary); }}
                .validation-error {{
                    background: rgba(239, 68, 68, 0.1);
                    border: 1px solid var(--error);
                    color: var(--error);
                    padding: 8px 12px;
                    border-radius: 6px;
                    margin-top: 10px;
                    font-size: 0.85rem;
                }}
                .form-group {{
                    margin-bottom: 12px;
                }}
                .form-group label {{
                    display: block;
                    margin-bottom: 6px;
                    color: var(--text-muted);
                    font-size: 0.85rem;
                }}
                .form-input {{
                    width: 100%;
                    padding: 10px 12px;
                    background: #0f172a;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    color: var(--text);
                    font-size: 0.95rem;
                }}
                .form-input:focus {{ outline: none; border-color: var(--primary); }}
                .editor-actions {{
                    display: flex;
                    gap: 10px;
                    margin-top: 12px;
                    justify-content: flex-end;
                }}
                .btn-primary {{
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-primary:hover {{ opacity: 0.9; }}
                .btn-secondary {{
                    background: var(--border);
                    color: var(--text);
                    border: none;
                    padding: 8px 20px;
                    border-radius: 6px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                .btn-secondary:hover {{ background: #475569; }}
                .btn-icon {{
                    padding: 4px 8px;
                    border: none;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                    margin: 0 2px;
                }}
                .btn-icon.edit {{
                    background: #3b82f6;
                    color: white;
                }}
                .btn-icon.edit:hover {{ background: #2563eb; }}
                .btn-icon.delete {{
                    background: #ef4444;
                    color: white;
                }}
                .btn-icon.delete:hover {{ background: #dc2626; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {body}
        </body>
        </html>
        """


def run_server_env(port=8000, env_dir="develop-saas"):
    """Run server for host-grouped partials (develop-saas structure)"""
    handler = EnvAPIRequestHandler
    
    class CustomServer(socketserver.ThreadingTCPServer):
        def __init__(self, *args, **kwargs):
            self.config_dir = env_dir
            super().__init__(*args, **kwargs)

    try:
        with CustomServer(("", port), handler) as httpd:
            print(f"Serving at http://localhost:{port}")
            print(f"Reading host-grouped config from: {env_dir}/")
            
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
                httpd.shutdown()
    except OSError as e:
        print(f"Error starting server on port {port}: {e}")

def merge(output_file="apigateway.json", config_dir="config"):
    """
    Merges partial configurations back into a single apigateway.json.
    """
    settings_dir = os.path.join(config_dir, "settings")
    partials_dir = os.path.join(config_dir, "partials")
    
    # 1. Read service.json for base fields
    service_file = os.path.join(settings_dir, "service.json")
    if not os.path.exists(service_file):
        print(f"Error: Service file '{service_file}' not found.")
        sys.exit(1)
        
    try:
        with open(service_file, 'r') as f:
            service_data = json.load(f)
    except Exception as e:
        print(f"Error reading service.json: {e}")
        sys.exit(1)
        
    # 2. Read global_extra_config.tmpl
    extra_config_file = os.path.join(partials_dir, "global_extra_config.tmpl")
    extra_config = {}
    if os.path.exists(extra_config_file):
        try:
            with open(extra_config_file, 'r') as f:
                content = f.read()
                # Wrap in braces to make it valid JSON
                json_content = "{" + content + "}"
                extra_config = json.loads(json_content)
        except Exception as e:
             print(f"Warning: Could not parse global_extra_config.tmpl: {e}")
    else:
        print(f"Warning: '{extra_config_file}' not found.")

    # 3. Read endpoint.json to get the list of endpoints/IDs
    endpoint_file = os.path.join(settings_dir, "endpoint.json")
    if not os.path.exists(endpoint_file):
        print(f"Error: Endpoint file '{endpoint_file}' not found.")
        sys.exit(1)
        
    try:
        with open(endpoint_file, 'r') as f:
            endpoint_mapping = json.load(f)
            mapping_group = endpoint_mapping.get("mapping_group", [])
    except Exception as e:
        print(f"Error reading endpoint.json: {e}")
        sys.exit(1)

    # 4. Construct the final endpoints list
    endpoints = []
    print(f"Merging {len(mapping_group)} endpoints...")
    
    for item in mapping_group:
        conn_id = item.get("id")
        partial_file = os.path.join(partials_dir, str(conn_id))
        
        if os.path.exists(partial_file):
            try:
                with open(partial_file, 'r') as f:
                    endpoint_data = json.load(f)
                    endpoints.append(endpoint_data)
            except Exception as e:
                print(f"  Error reading partial {conn_id}: {e}")
        else:
            print(f"  Warning: Partial file for ID {conn_id} not found.")

    # 5. Assemble final JSON
    final_data = {
        "version": 3, # Assuming version 3 based on typical Krakend/Lura configs or from input
        "name": service_data.get("name"),
        "port": service_data.get("port"),
        "cache_ttl": service_data.get("cache_ttl"),
        "timeout": service_data.get("timeout"),
        "extra_config": extra_config,
        "endpoints": endpoints
    }

    # Write to output file
    try:
        with open(output_file, 'w') as f:
            json.dump(final_data, f, indent=4)
        print(f"Successfully merged configuration into '{output_file}'")
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

# --- Endpoint CRUD Implementation ---

def get_config_paths(config_dir):
    return {
        "settings": os.path.join(config_dir, "settings"),
        "partials": os.path.join(config_dir, "partials"),
        "index_file": os.path.join(config_dir, "settings", "endpoint.json")
    }

def check_krakend(config_dir="config", template="krakend.tmpl"):
    """
    Validate KrakenD configuration using krakend check command.
    Returns list of tuples: (step_name, return_code, stdout, stderr)
    """
    results = []
    
    # Step 1: Validate template and generate temp file
    env = os.environ.copy()
    env.update({
        "FC_ENABLE": "1",
        "FC_OUT": "/tmp/test-config.json",
        "FC_PARTIALS": f"./{config_dir}/partials",
        "FC_SETTINGS": f"./{config_dir}/settings"
    })
    
    try:
        result1 = subprocess.run(
            ["krakend", "check", "-d", "-t", "-c", template],
            capture_output=True, text=True, env=env
        )
        results.append({
            "step": "Template Validation",
            "success": result1.returncode == 0,
            "output": result1.stdout,
            "error": result1.stderr
        })
    except FileNotFoundError:
        results.append({
            "step": "Template Validation",
            "success": False,
            "output": "",
            "error": "krakend command not found. Please ensure KrakenD is installed."
        })
        return results
    
    # Step 2: Check generated file
    try:
        result2 = subprocess.run(
            ["krakend", "check", "-c", "/tmp/test-config.json"],
            capture_output=True, text=True
        )
        results.append({
            "step": "Config Syntax Check",
            "success": result2.returncode == 0,
            "output": result2.stdout,
            "error": result2.stderr
        })
    except FileNotFoundError:
        results.append({
            "step": "Config Syntax Check",
            "success": False,
            "output": "",
            "error": "krakend command not found."
        })
    
    return results

def cmd_check_krakend(args):
    """CLI handler for check command."""
    results = check_krakend(config_dir=args.config_dir, template=args.template)
    
    all_success = True
    for r in results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        print(f"\n{status} - {r['step']}")
        if r["output"]:
            print(r["output"])
        if r["error"] and not r["success"]:
            print(f"Error: {r['error']}")
        if not r["success"]:
            all_success = False
    
    if all_success:
        print("\n✅ All checks passed!")
    else:
        print("\n❌ Some checks failed.")
        sys.exit(1)

def load_endpoint_index(config_dir):
    paths = get_config_paths(config_dir)
    if not os.path.exists(paths["index_file"]):
        return {"mapping_group": []}
    
    try:
        with open(paths["index_file"], 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading endpoint index: {e}")
        sys.exit(1)

def save_endpoint_index(config_dir, data):
    paths = get_config_paths(config_dir)
    os.makedirs(paths["settings"], exist_ok=True)
    try:
        with open(paths["index_file"], 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving endpoint index: {e}")
        sys.exit(1)

def get_next_id(config_dir):
    data = load_endpoint_index(config_dir)
    max_id = 0
    for item in data.get("mapping_group", []):
        try:
            curr_id = int(item.get("id", 0))
            if curr_id > max_id:
                max_id = curr_id
        except ValueError:
            continue # Skip non-integer IDs if any
    return str(max_id + 1)

def create_endpoint(config_dir, full_data):
    paths = get_config_paths(config_dir)
    
    # 1. Get Next ID
    next_id = get_next_id(config_dir)

    # 2. Use Full Data directly (ensure it's deep copied if modifying)
    endpoint_data = full_data.copy()
    if 'id' in endpoint_data:
        del endpoint_data['id'] # clean id from content if present

    # 3. Write Partial File
    partial_file = os.path.join(paths["partials"], next_id)
    os.makedirs(paths["partials"], exist_ok=True)
    try:
        with open(partial_file, 'w') as f:
            json.dump(endpoint_data, f, indent=2)
    except Exception as e:
        raise Exception(f"Error creating partial file: {e}")

    # 4. Extract fields for Index
    # Safe extraction of backend info
    host = ""
    private_endpoint = ""
    backends = endpoint_data.get("backend", [])
    if backends and len(backends) > 0:
        hosts = backends[0].get("host", [])
        if hosts and len(hosts) > 0:
            host = hosts[0]
        private_endpoint = backends[0].get("url_pattern", "")

    # 5. Update Index
    index_data = load_endpoint_index(config_dir)
    new_mapping = {
        "id": next_id,
        "endpoint": endpoint_data.get("endpoint", ""),
        "method": endpoint_data.get("method", "GET").upper(),
        "host": host,
        "private_endpoint": private_endpoint
    }
    index_data["mapping_group"].append(new_mapping)
    save_endpoint_index(config_dir, index_data)
    
    return next_id

def modify_endpoint(config_dir, target_id, full_data=None, endpoint=None, method=None, host=None, private_endpoint=None):
    paths = get_config_paths(config_dir)
    
    # Support legacy/CLI args via constructing a partial if full_data not provided
    if full_data is None:
        # Load existing to merge or construct minimal (here we assume CLI might use this path differently or we adapt CLI later)
        # For now, if called from CLI kwargs, we might need to load and update.
        # But to keep it simple and strictly follow the plan for UI:
        raise Exception("modify_endpoint requires full_data for UI operations")

    # 1. Write Partial File (Full Overwrite with new data)
    partial_file = os.path.join(paths["partials"], target_id)
    
    # Ensure ID is not in the file content to avoid redundancy/confusion
    endpoint_data = full_data.copy()
    if 'id' in endpoint_data:
        del endpoint_data['id']

    try:
        with open(partial_file, 'w') as f:
            json.dump(endpoint_data, f, indent=2)
    except Exception as e:
        raise Exception(f"Error updating partial file: {e}")

    # 2. Update Index
    index_data = load_endpoint_index(config_dir)
    found_item = None
    
    # Extract fields for Index
    host_val = ""
    private_endpoint_val = ""
    backends = endpoint_data.get("backend", [])
    if backends and len(backends) > 0:
        hosts = backends[0].get("host", [])
        if hosts and len(hosts) > 0:
            host_val = hosts[0]
        private_endpoint_val = backends[0].get("url_pattern", "")

    for item in index_data["mapping_group"]:
        if item.get("id") == target_id:
            found_item = item
            item["endpoint"] = endpoint_data.get("endpoint", "")
            item["method"] = endpoint_data.get("method", "GET").upper()
            item["host"] = host_val
            item["private_endpoint"] = private_endpoint_val
            break
            
    if not found_item:
        raise Exception(f"Endpoint ID {target_id} not found.")
        
    save_endpoint_index(config_dir, index_data)

def remove_endpoint(config_dir, target_id):
    paths = get_config_paths(config_dir)
    
    # 1. Remove from Index
    index_data = load_endpoint_index(config_dir)
    original_count = len(index_data["mapping_group"])
    index_data["mapping_group"] = [item for item in index_data["mapping_group"] if item.get("id") != target_id]
    
    if len(index_data["mapping_group"]) == original_count:
        raise Exception(f"Endpoint ID {target_id} not found in index.")
        
    save_endpoint_index(config_dir, index_data)
    
    # 2. Delete Partial File
    partial_file = os.path.join(paths["partials"], target_id)
    if os.path.exists(partial_file):
        try:
            os.remove(partial_file)
        except Exception as e:
            raise Exception(f"Error deleting partial file: {e}")

# --- Migrate-NS and Merge-NS Functions ---

def host_to_filename(host: str) -> str:
    """Convert host:port to filename format."""
    return host.replace("http://", "").replace(":", "-") + ".json"

def migrate_ns(input_file="apigateway.json", output_dir="develop-saas"):
    """
    Migrate apigateway.json to host-grouped partials format.
    Groups endpoints by backend host into separate JSON files.
    """
    from collections import defaultdict
    
    # Load input file
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    endpoints = data.get('endpoints', [])
    extra_config = data.get('extra_config', {})
    
    # Group endpoints by host
    host_groups = defaultdict(list)
    
    for ep in endpoints:
        backend = ep.get('backend', [])
        if backend and len(backend) > 0:
            hosts = backend[0].get('host', [])
            if hosts and len(hosts) > 0:
                host = hosts[0]
                host_groups[host].append(ep)
            else:
                host_groups['unknown'].append(ep)
        else:
            host_groups['unknown'].append(ep)
    
    # Create output directories
    partials_dir = os.path.join(output_dir, "partials")
    settings_dir = os.path.join(output_dir, "settings")
    os.makedirs(partials_dir, exist_ok=True)
    os.makedirs(settings_dir, exist_ok=True)
    
    # Create host-grouped partial files
    mapping_group = []
    total_endpoints = 0
    
    for host, eps in sorted(host_groups.items()):
        filename = host_to_filename(host)
        output_path = os.path.join(partials_dir, filename)
        
        with open(output_path, 'w') as f:
            json.dump(eps, f, indent=2)
        
        mapping_group.append({"id": filename})
        total_endpoints += len(eps)
        print(f"Created {filename} with {len(eps)} endpoints")
    
    # Create endpoint.json mapping
    endpoint_json = {"mapping_group": mapping_group}
    with open(os.path.join(settings_dir, "endpoint.json"), 'w') as f:
        json.dump(endpoint_json, f, indent=2)
    
    # Create service.json with base config
    service_json = {
        "name": data.get('name', 'API Gateway'),
        "port": data.get('port', 8005),
        "cache_ttl": data.get('cache_ttl', '300s'),
        "timeout": data.get('timeout', '9s')
    }
    with open(os.path.join(settings_dir, "service.json"), 'w') as f:
        json.dump(service_json, f, indent=2)
    
    # Create global_extra_config.tmpl if extra_config exists
    if extra_config:
        extra_config_path = os.path.join(partials_dir, "global_extra_config.tmpl")
        # Format: individual key-value pairs without outer braces (template adds them)
        lines = []
        items = list(extra_config.items())
        for i, (key, value) in enumerate(items):
            value_str = json.dumps(value, indent=2)
            # Indent the value properly
            value_lines = value_str.split('\n')
            indented_value = '\n  '.join(value_lines)
            line = f'  "{key}": {indented_value}'
            if i < len(items) - 1:
                line += ','
            lines.append(line)
        extra_config_content = '\n'.join(lines) + '\n'
        with open(extra_config_path, 'w') as f:
            f.write(extra_config_content)
        print(f"Created global_extra_config.tmpl")
    
    # Ensure apigateway.tmpl exists
    tmpl_path = os.path.join(output_dir, "apigateway.tmpl")
    if not os.path.exists(tmpl_path):
        default_tmpl = """{
    "$id": "https://www.krakend.io/schema/v3.json",
    "version": 3,
    "name": "{{ .service.name }}",
    "port": {{ .service.port }},
    "cache_ttl": "{{ .service.cache_ttl }}",
    "timeout": "{{ .service.timeout }}",
    "extra_config": {
        {{ include "global_extra_config.tmpl" }}
    },
    "endpoints": [
        {{ range $idx, $group := .endpoint.mapping_group }}
        {{if $idx}},{{end}}
        {{ $content := include $group.id }}
        {{ $trimmed := trimPrefix "[" $content }}
        {{ $trimmed = trimSuffix "]" $trimmed }}
        {{ $trimmed }}
        {{ end }}
    ],
    "output_encoding": "no-op"
}"""
        with open(tmpl_path, 'w') as f:
            f.write(default_tmpl)
        print("Created apigateway.tmpl")

    print(f"\n✅ Migration complete!")
    print(f"   Total hosts: {len(mapping_group)}")
    print(f"   Total endpoints: {total_endpoints}")
    print(f"   Output directory: {output_dir}")
    
    # Generate kustomization.yaml
    generate_kustomization(output_dir, data.get('name', 'API Gateway'))

def generate_kustomization(output_dir, service_name="API Gateway"):
    """
    Generate kustomization.yaml for the migrated namespace environment.
    Creates ConfigMaps for each partial file and patches deployment/service.
    """
    env_name = os.path.basename(output_dir)
    kustom_path = os.path.join(output_dir, "kustomization.yaml")
    if os.path.exists(kustom_path):
        print(f"Skipping kustomization.yaml generation (file exists)")
        return

    partials_dir = os.path.join(output_dir, "partials")
    
    # Get all partial files
    partial_files = []
    if os.path.exists(partials_dir):
        partial_files = sorted([f for f in os.listdir(partials_dir) if f.endswith('.json')])
    
    has_extra_config = os.path.exists(os.path.join(partials_dir, "global_extra_config.tmpl"))
    
    # Kustomization YAML content construction
    kustomization_content = f"""apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: {env_name}

resources:
  - ../base

# =============================================================================
# ConfigMap generator - 1 host = 1 configmap (matched to file name)
# =============================================================================
configMapGenerator:
"""
    
    # Global extra config
    if has_extra_config:
        kustomization_content += """  - name: global-extra-config
    files:
      - partials/global_extra_config.tmpl

"""
    
    # Host partials
    for p_file in partial_files:
        name = os.path.splitext(p_file)[0]
        kustomization_content += f"""  - name: {name}
    files:
      - partials/{p_file}

"""

    # Settings and Template
    kustomization_content += f"""  # Settings
  - name: krakend-settings
    files:
      - settings/endpoint.json
      - settings/service.json

  # Main Template
  - name: krakend-template
    files:
      - apigateway.tmpl

# =============================================================================
# Patches
# =============================================================================
patches:
  - target:
      kind: Deployment
      name: saas-apigateway
    patch: |-
      - op: replace
        path: /metadata/name
        value: saas-apigateway-{env_name}
      - op: replace
        path: /metadata/labels/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/selector/matchLabels/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/template/metadata/labels/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/template/spec/containers/0/name
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/template/spec/containers/0/image
        value: krakend:latest
      - op: replace
        path: /spec/template/spec/containers/0/ports/0/containerPort
        value: 8005
      - op: replace
        path: /spec/template/spec/containers/0/command
        value:
          - /bin/sh
          - -c
          - cd /etc/krakend && krakend run -c apigateway.tmpl
      - op: add
        path: /spec/template/spec/containers/0/env
        value:
          - name: FC_ENABLE
            value: "1"
          - name: FC_PARTIALS
            value: "partials"
          - name: FC_SETTINGS
            value: "settings"
      - op: add
        path: /spec/template/spec/containers/0/volumeMounts/-
        value:
          name: krakend-template
          mountPath: /etc/krakend
      - op: add
        path: /spec/template/spec/containers/0/volumeMounts/-
        value:
          name: krakend-partials
          mountPath: /etc/krakend/partials
      - op: add
        path: /spec/template/spec/containers/0/volumeMounts/-
        value:
          name: krakend-settings
          mountPath: /etc/krakend/settings
      - op: add
        path: /spec/template/spec/volumes/-
        value:
          name: krakend-partials
          projected:
            sources:
"""
    
    # Add projected volume sources
    if has_extra_config:
        kustomization_content += "              - configMap:\n                  name: global-extra-config\n"
        
    for p_file in partial_files:
        name = os.path.splitext(p_file)[0]
        kustomization_content += f"              - configMap:\n                  name: {name}\n"

    kustomization_content += f"""      - op: add
        path: /spec/template/spec/volumes/-
        value:
          name: krakend-settings
          configMap:
            name: krakend-settings
      - op: add
        path: /spec/template/spec/volumes/-
        value:
          name: krakend-template
          configMap:
            name: krakend-template

  - target:
      kind: Service
      name: saas-apigateway
    patch: |-
      - op: replace
        path: /metadata/name
        value: saas-apigateway-{env_name}
      - op: replace
        path: /metadata/labels/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/selector/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/ports/0/nodePort
        value: 8005
      - op: replace
        path: /spec/ports/0/port
        value: 8005

  - target:
      kind: Service
      name: saas-apigateway-metrics
    patch: |-
      - op: replace
        path: /metadata/name
        value: saas-apigateway-{env_name}-metrics
      - op: replace
        path: /metadata/labels/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/selector/app
        value: saas-apigateway-{env_name}
      - op: replace
        path: /spec/ports/0/nodePort
        value: 8015
      - op: replace
        path: /spec/ports/0/port
        value: 9090

commonLabels:
  app.kubernetes.io/instance: {env_name}
"""
    
    kustom_path = os.path.join(output_dir, "kustomization.yaml")
    try:
        with open(kustom_path, 'w') as f:
            f.write(kustomization_content)
        print(f"Created kustomization.yaml in {output_dir}")
    except Exception as e:
        print(f"Error creating kustomization.yaml: {e}")



def merge_ns(input_dir="develop-saas", output_file="apigateway.json"):
    """
    Merge host-grouped partials back to single apigateway.json.
    Combines all endpoint files into a single configuration.
    """
    partials_dir = os.path.join(input_dir, "partials")
    settings_dir = os.path.join(input_dir, "settings")
    
    # Load service.json for base config
    service_path = os.path.join(settings_dir, "service.json")
    if os.path.exists(service_path):
        with open(service_path, 'r') as f:
            service_data = json.load(f)
    else:
        service_data = {
            "name": "API Gateway",
            "port": 8005,
            "cache_ttl": "300s",
            "timeout": "9s"
        }
    
    # Load endpoint.json for mapping
    endpoint_path = os.path.join(settings_dir, "endpoint.json")
    with open(endpoint_path, 'r') as f:
        endpoint_data = json.load(f)
    
    # Collect all endpoints from host files
    all_endpoints = []
    
    for item in endpoint_data.get('mapping_group', []):
        host_file = item.get('id', '')
        host_path = os.path.join(partials_dir, host_file)
        
        if os.path.exists(host_path):
            with open(host_path, 'r') as f:
                endpoints = json.load(f)
                if isinstance(endpoints, list):
                    all_endpoints.extend(endpoints)
                    print(f"Loaded {len(endpoints)} endpoints from {host_file}")
        else:
            print(f"Warning: {host_file} not found")
    
    # Load extra_config from global_extra_config.tmpl if exists
    extra_config = {}
    extra_config_path = os.path.join(partials_dir, "global_extra_config.tmpl")
    if os.path.exists(extra_config_path):
        with open(extra_config_path, 'r') as f:
            content = f.read()
            try:
                extra_config = json.loads(content)
            except json.JSONDecodeError:
                print("Warning: Could not parse global_extra_config.tmpl as JSON")
    
    # Build final config
    output_data = {
        "$id": "https://www.krakend.io/schema/v3.json",
        "version": 3,
        "name": service_data.get('name', 'API Gateway'),
        "port": service_data.get('port', 8005),
        "cache_ttl": service_data.get('cache_ttl', '300s'),
        "timeout": service_data.get('timeout', '9s'),
    }
    
    if extra_config:
        output_data["extra_config"] = extra_config
    
    output_data["endpoints"] = all_endpoints
    
    # Write output file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=4)
    
    print(f"\n✅ Merge complete!")
    print(f"   Total endpoints: {len(all_endpoints)}")
    print(f"   Output file: {output_file}")


def check_ns(ns_dir="develop-saas", template=None):
    """
    Run KrakenD check for host-grouped partials directory.
    Dynamically uses {ns_dir}.tmpl as template if not specified.
    """
    import subprocess
    
    # Determine template file
    if template is None:
        template = os.path.join(ns_dir, "apigateway.tmpl")
    
    partials_dir = os.path.join(ns_dir, "partials")
    settings_dir = os.path.join(ns_dir, "settings")
    
    # Verify directories exist
    if not os.path.exists(partials_dir):
        print(f"❌ Error: {partials_dir} does not exist")
        sys.exit(1)
    if not os.path.exists(settings_dir):
        print(f"❌ Error: {settings_dir} does not exist")
        sys.exit(1)
    if not os.path.exists(template):
        print(f"❌ Error: Template {template} does not exist")
        sys.exit(1)
    
    print(f"Checking KrakenD config...")
    print(f"  Template: {template}")
    print(f"  Partials: {partials_dir}")
    print(f"  Settings: {settings_dir}")
    print()
    
    # Run krakend check
    env = os.environ.copy()
    env["FC_ENABLE"] = "1"
    env["FC_PARTIALS"] = partials_dir
    env["FC_SETTINGS"] = settings_dir
    
    try:
        result = subprocess.run(
            ["krakend", "check", "-t", "-c", template],
            env=env,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Syntax OK!")
        else:
            print("❌ Check failed!")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: krakend command not found. Please install KrakenD.")
        sys.exit(1)


def match_ns(input_file="apigateway.json", ns_dir="develop-saas"):
    """
    Compare apigateway.json endpoints with host-grouped partials.
    Reports differences between the two sources.
    """
    from collections import defaultdict
    
    # Load apigateway.json
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} does not exist")
        sys.exit(1)
    
    with open(input_file, 'r') as f:
        source_data = json.load(f)
    
    source_endpoints = source_data.get('endpoints', [])
    
    # Load partials from ns_dir
    partials_dir = os.path.join(ns_dir, "partials")
    settings_dir = os.path.join(ns_dir, "settings")
    endpoint_path = os.path.join(settings_dir, "endpoint.json")
    
    if not os.path.exists(endpoint_path):
        print(f"❌ Error: {endpoint_path} does not exist")
        sys.exit(1)
    
    with open(endpoint_path, 'r') as f:
        endpoint_data = json.load(f)
    
    # Collect all endpoints from partials
    partial_endpoints = []
    for item in endpoint_data.get('mapping_group', []):
        host_file = item.get('id', '')
        host_path = os.path.join(partials_dir, host_file)
        if os.path.exists(host_path):
            with open(host_path, 'r') as f:
                endpoints = json.load(f)
                if isinstance(endpoints, list):
                    partial_endpoints.extend(endpoints)
    
    # Create endpoint signatures for comparison
    def endpoint_signature(ep):
        method = ep.get('method', 'GET')
        path = ep.get('endpoint', '')
        return f"{method}:{path}"
    
    source_sigs = {endpoint_signature(ep) for ep in source_endpoints}
    partial_sigs = {endpoint_signature(ep) for ep in partial_endpoints}
    
    # Find differences
    only_in_source = source_sigs - partial_sigs
    only_in_partials = partial_sigs - source_sigs
    common = source_sigs & partial_sigs
    
    print(f"📊 Comparison: {input_file} vs {ns_dir}/")
    print(f"{'='*50}")
    print(f"  Source endpoints ({input_file}): {len(source_endpoints)}")
    print(f"  Partial endpoints ({ns_dir}/): {len(partial_endpoints)}")
    print(f"{'='*50}")
    print(f"  ✅ Matching endpoints: {len(common)}")
    
    if only_in_source:
        print(f"\n  ⚠️  Only in {input_file} ({len(only_in_source)}):")
        for sig in sorted(only_in_source)[:10]:
            print(f"      - {sig}")
        if len(only_in_source) > 10:
            print(f"      ... and {len(only_in_source) - 10} more")
    
    if only_in_partials:
        print(f"\n  ⚠️  Only in {ns_dir}/ ({len(only_in_partials)}):")
        for sig in sorted(only_in_partials)[:10]:
            print(f"      - {sig}")
        if len(only_in_partials) > 10:
            print(f"      ... and {len(only_in_partials) - 10} more")
    
    if not only_in_source and not only_in_partials:
        print(f"\n✅ Perfect match! All endpoints are synchronized.")
    else:
        print(f"\n❌ Mismatch detected!")
        sys.exit(1)


def cmd_add_endpoint(args):
    try:
        next_id = create_endpoint(args.config_dir, args.endpoint, args.method, args.host, args.private_endpoint)
        print(f"Creating endpoint with ID: {next_id}")
        print(f"Created partial file: config/partials/{next_id}")
        print(f"Added to endpoint index: config/settings/endpoint.json")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_update_endpoint(args):
    try:
        modify_endpoint(args.config_dir, args.id, args.endpoint, args.method, args.host, args.private_endpoint)
        print(f"Updated endpoint {args.id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_delete_endpoint(args):
    try:
        remove_endpoint(args.config_dir, args.id)
        print(f"Removed ID {args.id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="API Gateway CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Migrate-v1 command (Legacy)
    migrate_v1_parser = subparsers.add_parser('migrate-v1', help='Migrate apigateway.json to partial config (Legacy)')
    migrate_v1_parser.add_argument('--input', '-i', default='apigateway.json', help='Input JSON file')
    migrate_v1_parser.add_argument('--config-dir', '-d', default='config', help='Output configuration directory')

    # Server-v1 command (Legacy)
    server_v1_parser = subparsers.add_parser('server-v1', help='Start web server to view configuration (Legacy)')
    server_v1_parser.add_argument('--port', '-p', type=int, default=8000, help='Port to run server on')
    server_v1_parser.add_argument('--config-dir', '-d', default='config', help='Configuration directory to read from')

    # Server command (formerly server-ns)
    server_parser = subparsers.add_parser('server', help='Start web server for host-grouped partials (develop-saas style)')
    server_parser.add_argument('env_dir', nargs='?', default='develop-saas', help='Environment directory (e.g. develop-saas)')
    server_parser.add_argument('--port', '-p', type=int, default=8000, help='Port to run server on')

    # Merge-v1 command (Legacy)
    merge_v1_parser = subparsers.add_parser('merge-v1', help='Merge partial config into apigateway.json (Legacy)')
    merge_v1_parser.add_argument('--file', '-f', default='apigateway.json', help='Output JSON file')
    merge_v1_parser.add_argument('--config-dir', '-d', default='config', help='Configuration directory to read from')

    # Check-v1 command (Legacy)
    check_v1_parser = subparsers.add_parser('check-v1', help='Validate KrakenD configuration (Legacy)')
    check_v1_parser.add_argument('--config-dir', '-d', default='config', help='Configuration directory')
    check_v1_parser.add_argument('--template', '-t', default='krakend.tmpl', help='KrakenD template file')

    # Migrate command (formerly migrate-ns)
    migrate_parser = subparsers.add_parser('migrate', help='Migrate apigateway.json to host-grouped partials format')
    migrate_parser.add_argument('output_dir', nargs='?', default='develop-saas', help='Output directory for partials')
    migrate_parser.add_argument('--input', '-i', default='apigateway.json', help='Input JSON file')

    # Merge command (formerly merge-ns)
    merge_parser = subparsers.add_parser('merge', help='Merge host-grouped partials back to apigateway.json')
    merge_parser.add_argument('input_dir', nargs='?', default='develop-saas', help='Input directory with partials')
    merge_parser.add_argument('--output', '-o', default='apigateway.json', help='Output JSON file')

    # Check command (formerly check-ns)
    check_parser = subparsers.add_parser('check', help='Validate KrakenD config for host-grouped partials')
    check_parser.add_argument('ns_dir', nargs='?', default='develop-saas', help='Namespace directory with partials')
    check_parser.add_argument('--template', '-t', help='Template file (default: {ns_dir}.tmpl)')

    # Match command (formerly match-ns)
    match_parser = subparsers.add_parser('match', help='Compare apigateway.json with host-grouped partials')
    match_parser.add_argument('ns_dir', nargs='?', default='develop-saas', help='Namespace directory with partials')
    match_parser.add_argument('--input', '-i', default='apigateway.json', help='Source JSON file to compare')

    # Endpoint (CRUD) command - DISABLED
    # Usage: endpoint add, endpoint update, endpoint delete
    # Alias: ep
    # ep_parser = subparsers.add_parser('endpoint', aliases=['ep'], help='Manage endpoints (CRUD)')
    # ep_subparsers = ep_parser.add_subparsers(dest='ep_command', required=True)

    # endpoint add
    # add_parser = ep_subparsers.add_parser('add', help='Add a new endpoint')
    # add_parser.add_argument('--config-dir', '-d', default='config')
    # add_parser.add_argument('--endpoint', '-e', required=True, help='Public endpoint URL (e.g. /api/foo)')
    # add_parser.add_argument('--method', '-m', required=True, help='HTTP Method (GET, POST etc)')
    # add_parser.add_argument('--host', '-H', required=True, help='Backend host (e.g. localhost:8080)')
    # add_parser.add_argument('--private-endpoint', '-p', required=True, help='Backend URL pattern')

    # endpoint update
    # update_parser = ep_subparsers.add_parser('update', help='Update an existing endpoint')
    # update_parser.add_argument('id', help='Endpoint ID')
    # update_parser.add_argument('--config-dir', '-d', default='config')
    # update_parser.add_argument('--endpoint', '-e', help='New public endpoint URL')
    # update_parser.add_argument('--method', '-m', help='New HTTP Method')
    # update_parser.add_argument('--host', '-H', help='New backend host')
    # update_parser.add_argument('--private-endpoint', '-p', help='New backend URL pattern')

    # endpoint delete
    # delete_parser = ep_subparsers.add_parser('delete', help='Delete an endpoint')
    # delete_parser.add_argument('id', help='Endpoint ID')
    # delete_parser.add_argument('--config-dir', '-d', default='config')

    args = parser.parse_args()

    if args.command == 'migrate-v1':
        migrate(input_file=args.input, config_dir=args.config_dir)
    elif args.command == 'server-v1':
        run_server(port=args.port, config_dir=args.config_dir)
    elif args.command == 'server':
        run_server_env(port=args.port, env_dir=args.env_dir)
    elif args.command == 'merge-v1':
        merge(output_file=args.file, config_dir=args.config_dir)
    elif args.command == 'check-v1':
        cmd_check_krakend(args)
    elif args.command == 'migrate':
        migrate_ns(input_file=args.input, output_dir=args.output_dir)
    elif args.command == 'merge':
        merge_ns(input_dir=args.input_dir, output_file=args.output)
    elif args.command == 'check':
        check_ns(ns_dir=args.ns_dir, template=args.template)
    elif args.command == 'match':
        match_ns(input_file=args.input, ns_dir=args.ns_dir)
    # elif args.command in ['endpoint', 'ep']:
    #     if args.ep_command == 'add':
    #         cmd_add_endpoint(args)
    #     elif args.ep_command == 'update':
    #         cmd_update_endpoint(args)
    #     elif args.ep_command == 'delete':
    #         cmd_delete_endpoint(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
