{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    nixpkgs22.url = "github:nixos/nixpkgs/22.11";
    nixpkgsUnstable.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    flakeUtils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, nixpkgs22, nixpkgsUnstable, flakeUtils }:
    flakeUtils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs22 = nixpkgs22.legacyPackages.${system};
        pkgsUnstable = nixpkgsUnstable.legacyPackages.${system};
      in {
        packages = flakeUtils.lib.flattenTree {
          python313 = pkgs.python313;
          python312 = pkgs.python312;
          python311 = pkgs.python311;
          python310 = pkgs.python310;
          python39 = pkgs.python39;
          python38 = pkgs22.python38;
          go-task = pkgsUnstable.go-task;
        };
        devShell = pkgs.mkShell {
          buildInputs = with self.packages.${system}; [
            python313
            python312
            python311
            python310
            python39
            python38
            go-task
          ];
          shellHook = ''
            [[ ! -d .venv ]] && \
              echo "Creating virtualenv ..." && \
              ${pkgs.python310}/bin/python -m \
                venv --copies --upgrade-deps .venv > /dev/null
            source .venv/bin/activate
          '';
        };
      }
    );
}
