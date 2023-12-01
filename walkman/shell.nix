{ sources ? import ./nix/sources.nix, rsources ? import (sources.mutwo-nix.outPath + "/nix/sources.nix"), pkgs ? import rsources.nixpkgs {}}:

with pkgs;
with pkgs.python310Packages;

let

  walkman       = import (sources.mutwo-nix.outPath + "/walkman/default.nix") {};

  walkman_modules = buildPythonPackage rec {
    name = "walkman_modules.prologue";
    src = ./walkman_modules.prologue;
    checkInputs = [
      python310Packages.pytest
    ];
    propagatedBuildInputs = with pkgs.python310Packages; [ 
      walkman
    ];
    checkPhase = ''
      runHook preCheck
      pytest
      runHook postCheck
    '';
    doCheck = false;
  };

  mypython = python310.buildEnv.override {
    extraLibs = [
      ipython
      walkman
    walkman_modules
    ];
  };

in

  pkgs.mkShell {
      buildInputs = with pkgs; [
          mypython
      ];
  }
