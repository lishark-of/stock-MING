type Props = {
  title: string;
  data: unknown;
  open?: boolean;
};

export default function JsonDetails({ title, data, open = false }: Props) {
  return (
    <details className="json-details" open={open}>
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
