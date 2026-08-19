from getpass import getpass

from bip_utils import (
    Bip39MnemonicValidator,
    Bip39SeedGenerator,
)


EXPECTED_ADDRESS = "OQPPYZZNNFBQ664DX65YCIIVKDMAXNJ65T7MPSELNDYZ5PPRNUXBVQ6HUU"


def main():
    mnemonic = getpass("Enter your 24-word Pera recovery phrase: ")

    words = mnemonic.strip().split()

    if len(words) != 24:
        raise ValueError(
            f"Expected 24 words, received {len(words)}."
        )

    # Validate the BIP-39 mnemonic locally.
    Bip39MnemonicValidator().Validate(mnemonic)

    # Generate the BIP-39 seed locally.
    seed = Bip39SeedGenerator(mnemonic).Generate()

    print("\nBIP-39 mnemonic is valid.")
    print(f"Generated seed length: {len(seed)} bytes")

    print("\nIMPORTANT:")
    print("We have NOT derived or printed a private key yet.")
    print("The next step is determining the exact Pera Algorand")
    print("derivation path for the existing payer address.")
    print(f"\nExpected payer address:\n{EXPECTED_ADDRESS}")


if __name__ == "__main__":
    main()