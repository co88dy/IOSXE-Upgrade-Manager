{
  description = "IOS-XE Upgrade Manager with Poetry2Nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        
        # Create an environment from pyproject.toml and poetry.lock
        appEnv = p2n.mkPoetryApplication {
          projectDir = ../.;
          python = pkgs.python311;
          preferWheels = true;
        };
        
        # Create a shell environment with poetry for development
        devEnv = p2n.mkPoetryEnv {
          projectDir = ../.;
          python = pkgs.python311;
          editablePackageSources = {
            iosxe-upgrade-manager = ../.;
          };
        };

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            poetry
            devEnv
          ];

          shellHook = ''
            echo "IOS-XE Upgrade Manager (Poetry2Nix Environment)"
            echo "Python version: $(python --version)"
            echo ""
            echo "Development commands:"
            echo "  poetry install  # Install dependencies"
            echo "  poetry run python main.py # Run app"
          '';
        };

        packages.default = pkgs.dockerTools.buildLayeredImage {
          name = "ios-xe-upgrade-manager";
          tag = "latest";
          contents = [ appEnv pkgs.bash pkgs.coreutils ];
          config = {
            Cmd = [ "${appEnv}/bin/python" "main.py" ];
            WorkingDir = "/app";
            ExposedPorts = {
              "5000/tcp" = {};
              "80/tcp" = {};
            };
          };
        };
        
        # Expose the app package itself
        packages.app = appEnv;
      }
    );
}
