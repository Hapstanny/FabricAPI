"""List the Fabric workspaces visible to the signed-in identity."""

from fabric_api import FabricClient, TokenCredentialFactory


def main() -> None:
    credential = TokenCredentialFactory.from_environment().create()
    with FabricClient(credential) as client:
        for workspace in client.list_workspaces():
            print(f"{workspace.get('displayName', '<unnamed>')}\t{workspace.get('id', '')}")


if __name__ == "__main__":
    main()
