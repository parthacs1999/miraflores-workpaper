"use client";
import { useEffect, useState } from "react";
import { useWorkpaperIdentity } from "./session";
import { evidenceRequest } from "./evidence-types";
import { useAppNavigation } from "./shell/navigation";
import { StatusBadge } from "./ui/primitives";
type Attachment = {
  id: string;
  kind: string;
  state: string;
  data: {
    title: string;
    links: { kind: string; id: string }[];
    sha256?: string;
  };
};
export default function LinkedAttachments({
  kind,
  id,
}: {
  kind: string;
  id: string;
}) {
  const identity = useWorkpaperIdentity();
  const navigation = useAppNavigation();
  const [items, setItems] = useState<Attachment[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!identity) return;
    let active = true;
    evidenceRequest<{ items: Attachment[] }>("/api/product/overview")
      .then((d) => {
        if (active)
          setItems(
            d.items.filter(
              (a) =>
                a.kind === "p_attachment" &&
                a.data.links?.some((l) => l.kind === kind && l.id === id),
            ),
          );
      })
      .catch(() => {
        if (active) setError("Linked attachment metadata could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, [identity, kind, id]);
  if (!identity) return null;
  return (
    <section className="linked-attachments">
      <h4>Linked supporting attachments</h4>
      {error ? (
        <p role="alert">{error}</p>
      ) : items?.length ? (
        items.map((a) => (
          <button
            key={a.id}
            className="linked-attachment"
            onClick={() => navigation?.navigate("attachments", a.id)}
          >
            <span>{a.data.title}</span>
            <StatusBadge value={a.state} />
            <small>
              Unprocessed original · Purpose-audited download in Attachments
            </small>
          </button>
        ))
      ) : (
        <p className="muted">
          {items
            ? "No supporting attachments linked to this record."
            : "Loading linked metadata…"}
        </p>
      )}
    </section>
  );
}
