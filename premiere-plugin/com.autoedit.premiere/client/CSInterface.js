/**
 * CSInterface.js — minimal shim covering the subset used by AutoEdit.
 *
 * For production use, replace this file with the official Adobe CSInterface.js
 * from: https://github.com/Adobe-CEP/CEP-Resources/tree/master/CEP_11.x/CSInterface.js
 *
 * What this shim covers:
 *   - new CSInterface()
 *   - csInterface.evalScript(script, callback)
 *   - csInterface.getSystemPath(SystemPath.USER_DATA)
 *   - SystemPath constants
 */

var SystemPath = {
  USER_DATA:    "userData",
  APP_DATA:     "appData",
  EXTENSION:    "extension",
  DESKTOP:      "desktop",
  DOCUMENTS:    "documents",
};

function CSInterface() {
  this._cep = window.__adobe_cep__;
}

CSInterface.prototype.evalScript = function(script, callback) {
  if (this._cep) {
    this._cep.evalScript(script, callback || function() {});
  } else {
    console.warn("[CSInterface] evalScript: __adobe_cep__ not available");
    if (callback) callback("EvalScript error.");
  }
};

CSInterface.prototype.getSystemPath = function(pathType) {
  if (this._cep) {
    var info = JSON.parse(this._cep.getHostEnvironment());
    if (pathType === SystemPath.USER_DATA) {
      return info.appData || "";
    }
    if (pathType === SystemPath.EXTENSION) {
      return info.extensionRootPath || "";
    }
  }
  return "";
};

CSInterface.prototype.addEventListener = function(type, listener) {
  if (this._cep) this._cep.addEventListener(type, listener);
};
