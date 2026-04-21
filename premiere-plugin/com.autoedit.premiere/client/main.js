/**
 * main.js — AutoEdit CEP panel logic
 *
 * Flow:
 *  1. On load: read settings from localStorage, show setup or main UI
 *  2. User picks a video and clicks "Generate Rough Cut"
 *  3. Node.js child_process spawns: python main.py --input <video> --mode premiere
 *  4. Stdout lines stream into the log box + progress bar
 *  5. On success: show "Import into Premiere" button
 *  6. On click: evalScript calls host.jsx to import the XML into the open project
 */

(function () {
  "use strict";

  var csInterface = new CSInterface();
  var path = require("path");
  var os = require("os");
  var fs = require("fs");
  var child_process = require("child_process");

  // ── State ──────────────────────────────────────────────────────────────────
  var settings = {
    backendPath: "",   // path to autoedit-lite/ directory
    pythonPath: "",    // path to python executable
  };
  var lastXmlPath = "";
  var lastSrtPath = "";

  // ── DOM refs ───────────────────────────────────────────────────────────────
  var setupSection   = document.getElementById("setup-section");
  var mainSection    = document.getElementById("main-section");
  var btnChoose      = document.getElementById("btn-choose-backend");
  var btnBrowse      = document.getElementById("btn-browse");
  var inputVideo     = document.getElementById("input-video");
  var selectModel    = document.getElementById("select-model");
  var selectQuality  = document.getElementById("select-quality");
  var btnGenerate    = document.getElementById("btn-generate");
  var progressSection = document.getElementById("progress-section");
  var progressBar    = document.getElementById("progress-bar");
  var progressLabel  = document.getElementById("progress-label");
  var logBox         = document.getElementById("log-box");
  var logText        = document.getElementById("log-text");
  var resultSection  = document.getElementById("result-section");
  var resultMessage  = document.getElementById("result-message");
  var btnImport      = document.getElementById("btn-import");
  var btnReset       = document.getElementById("btn-reset");
  var btnSettings    = document.getElementById("btn-settings");

  // ── Settings helpers ───────────────────────────────────────────────────────
  function loadSettings() {
    try {
      var raw = localStorage.getItem("autoedit_settings");
      if (raw) settings = JSON.parse(raw);
    } catch (e) { /* ignore */ }
  }

  function saveSettings() {
    localStorage.setItem("autoedit_settings", JSON.stringify(settings));
  }

  function detectPython() {
    // Try common Python paths in order
    var candidates = (os.platform() === "win32")
      ? [
          "C:\\Program Files\\Python312\\python.exe",
          "C:\\Program Files\\Python311\\python.exe",
          "C:\\Program Files\\Python310\\python.exe",
          "python",
        ]
      : [
          "/opt/homebrew/bin/python3",
          "/usr/local/bin/python3",
          "/usr/bin/python3",
          "python3",
        ];

    for (var i = 0; i < candidates.length; i++) {
      try {
        var result = child_process.spawnSync(candidates[i], ["--version"]);
        if (result.status === 0) return candidates[i];
      } catch (e) { /* try next */ }
    }
    return (os.platform() === "win32") ? "python" : "python3";
  }

  function isConfigured() {
    return settings.backendPath &&
           fs.existsSync(path.join(settings.backendPath, "main.py"));
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  loadSettings();

  if (isConfigured()) {
    showMain();
  } else {
    showSetup();
  }

  // ── Setup flow ─────────────────────────────────────────────────────────────
  btnChoose.addEventListener("click", function () {
    // Open a folder picker via ExtendScript (Premiere's file dialog)
    csInterface.evalScript(
      'var f = Folder.selectDialog("Select your autoedit-lite folder"); f ? f.fsName : ""',
      function (selectedPath) {
        if (!selectedPath || selectedPath === "EvalScript error.") return;
        selectedPath = selectedPath.trim();
        if (!fs.existsSync(path.join(selectedPath, "main.py"))) {
          alert("That folder doesn't contain main.py.\nPlease select the autoedit-lite folder.");
          return;
        }
        settings.backendPath = selectedPath;
        settings.pythonPath = settings.pythonPath || detectPython();
        saveSettings();
        showMain();
      }
    );
  });

  // ── Settings button (re-show setup) ────────────────────────────────────────
  btnSettings.addEventListener("click", function () {
    showSetup();
  });

  // ── Browse for video ───────────────────────────────────────────────────────
  btnBrowse.addEventListener("click", function () {
    csInterface.evalScript(
      'var f = File.openDialog("Select a video file", "*.mp4;*.mov;*.mkv;*.webm", false); f ? f.fsName : ""',
      function (filePath) {
        if (!filePath || filePath === "EvalScript error.") return;
        filePath = filePath.trim();
        inputVideo.value = filePath;
        btnGenerate.disabled = false;
      }
    );
  });

  // ── Generate ───────────────────────────────────────────────────────────────
  btnGenerate.addEventListener("click", function () {
    var videoPath = inputVideo.value.trim();
    if (!videoPath) return;

    var videoDir  = path.dirname(videoPath);
    var videoBase = path.basename(videoPath, path.extname(videoPath));
    var outXml    = path.join(videoDir, videoBase + "_autoedit.xml");
    var outSrt    = path.join(videoDir, videoBase + "_autoedit.srt");

    lastXmlPath = outXml;
    lastSrtPath = outSrt;

    var mainPy  = path.join(settings.backendPath, "main.py");
    var python  = settings.pythonPath || detectPython();

    var args = [
      mainPy,
      "--input", videoPath,
      "--mode", "premiere",
      "--model", selectModel.value,
      "--quality", selectQuality.value,
      "--output", path.join(videoDir, videoBase + "_autoedit.mp4"),
    ];

    setRunningState(true);
    appendLog("Running: " + python + " " + args.join(" ") + "\n\n");

    var proc = child_process.spawn(python, args, {
      cwd: settings.backendPath,
    });

    var stepMap = {
      "[1/4]": 20,
      "[2/4]": 50,
      "[3/4]": 75,
      "[4/4]": 90,
    };

    proc.stdout.on("data", function (data) {
      var line = data.toString();
      appendLog(line);
      for (var key in stepMap) {
        if (line.indexOf(key) !== -1) setProgress(stepMap[key], line.replace(/\[.\/.\]\s*/, "").trim());
      }
    });

    proc.stderr.on("data", function (data) {
      appendLog("[stderr] " + data.toString());
    });

    proc.on("close", function (code) {
      setRunningState(false);
      if (code === 0 && fs.existsSync(outXml)) {
        setProgress(100, "Done");
        showResult(true, "Rough cut ready. " + path.basename(outXml));
      } else {
        setProgress(0, "");
        showResult(false, "Something went wrong. Check the log above for details.");
      }
    });

    proc.on("error", function (err) {
      setRunningState(false);
      showResult(false, "Could not start Python: " + err.message + "\n\nCheck Settings to confirm the Python path is correct.");
    });
  });

  // ── Import into Premiere ───────────────────────────────────────────────────
  btnImport.addEventListener("click", function () {
    if (!lastXmlPath) return;
    var script = 'importXmlSequence("' + lastXmlPath.replace(/\\/g, "\\\\") + '")';
    csInterface.evalScript(script, function (result) {
      if (result === "SUCCESS") {
        resultMessage.textContent = "Sequence imported into your Premiere project.";
        resultMessage.className = "success";
        btnImport.disabled = true;
      } else {
        resultMessage.textContent = "Auto-import failed. Please go to File → Import and choose:\n" + lastXmlPath;
        resultMessage.className = "error";
      }
    });
  });

  btnReset.addEventListener("click", resetUI);

  // ── UI helpers ─────────────────────────────────────────────────────────────
  function showSetup() {
    setupSection.classList.remove("hidden");
    mainSection.classList.add("hidden");
  }

  function showMain() {
    setupSection.classList.add("hidden");
    mainSection.classList.remove("hidden");
    progressSection.classList.add("hidden");
    logBox.classList.add("hidden");
    resultSection.classList.add("hidden");
  }

  function setRunningState(running) {
    btnGenerate.disabled = running;
    btnBrowse.disabled = running;
    progressSection.classList.toggle("hidden", !running);
    logBox.classList.toggle("hidden", !running);
    resultSection.classList.add("hidden");
    if (running) {
      progressBar.className = "progress-bar indeterminate";
      progressLabel.textContent = "Starting Python...";
      logText.textContent = "";
    }
  }

  function setProgress(pct, label) {
    progressBar.className = "progress-bar";
    progressBar.style.width = pct + "%";
    if (label) progressLabel.textContent = label;
  }

  function appendLog(text) {
    logText.textContent += text;
    logBox.scrollTop = logBox.scrollHeight;
  }

  function showResult(success, message) {
    resultSection.classList.remove("hidden");
    resultMessage.textContent = message;
    resultMessage.className = success ? "success" : "error";
    btnImport.style.display = success ? "block" : "none";
    btnImport.disabled = false;
  }

  function resetUI() {
    inputVideo.value = "";
    logText.textContent = "";
    lastXmlPath = "";
    lastSrtPath = "";
    btnGenerate.disabled = true;
    progressSection.classList.add("hidden");
    logBox.classList.add("hidden");
    resultSection.classList.add("hidden");
  }

})();
