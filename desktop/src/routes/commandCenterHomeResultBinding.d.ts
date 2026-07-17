export type OrdinaryHomeResultBindingSource = "candidate" | "storage";

export type OrdinaryHomeResultBinding = {
  source: OrdinaryHomeResultBindingSource;
  symbol: string;
  taskId: string;
  resultVersion: string;
  dataDate: string;
  freshness: string;
};

export type OrdinaryHomeConfirmedChain = {
  source: string;
  symbol: string;
  taskId: string;
};

export type HomeResultBindingFields = {
  symbol: string;
  taskId: string;
  resultVersion: string;
  dataDate: string;
  freshness: string;
};

export type HomeConfirmedChainFields = {
  symbol: string;
  taskId: string;
};

export function strictHomeSymbol(value: unknown): string;
export function strictHomeIdentity(value: unknown, maxLength?: number): string;
export function strictHomeFreshness(value: unknown): string;
export function strictHomeResultDate(value: unknown, options?: { allowIsoDate?: boolean }): string;
export function makeStrictHomeResultBinding(
  record: Record<string, unknown>,
  fields: HomeResultBindingFields,
  source: OrdinaryHomeResultBindingSource,
): OrdinaryHomeResultBinding | null;
export function sameOrdinaryHomeResultBinding(
  left: OrdinaryHomeResultBinding,
  right: OrdinaryHomeResultBinding,
): boolean;
export function selectMatchingHomeResultBinding(
  bindings: Array<OrdinaryHomeResultBinding | null>,
): { binding: OrdinaryHomeResultBinding | null; conflict: boolean };
export function makeStrictHomeConfirmedChain(
  record: Record<string, unknown>,
  fields: HomeConfirmedChainFields,
  source: string,
): OrdinaryHomeConfirmedChain | null;
export function selectMatchingHomeConfirmedChain(
  chains: Array<OrdinaryHomeConfirmedChain | null>,
): { chain: OrdinaryHomeConfirmedChain | null; conflict: boolean };
export function hasUnconfirmedHomeSymbolEdit(input: {
  touched: boolean;
  raw: unknown;
  valid: boolean;
  normalized: string;
  confirmedSymbol: string;
}): boolean;
