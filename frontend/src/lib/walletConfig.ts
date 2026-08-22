/**
 * Wallet provider configuration for @txnlab/use-wallet-react with Pera Wallet.
 * Configured for Algorand TestNet only.
 */
import { WalletManager } from '@txnlab/use-wallet';
import { pera } from '@txnlab/use-wallet-pera';

const TESTNET_NETWORK = 'testnet';

const walletManager = new WalletManager({
  wallets: [
    pera(),
  ],
  networks: {
    [TESTNET_NETWORK]: {
      algod: {
        token: '',
        baseServer: 'https://testnet-api.algonode.cloud',
        port: '',
      },
    },
  },
  defaultNetwork: TESTNET_NETWORK,
});

export { walletManager, TESTNET_NETWORK };
