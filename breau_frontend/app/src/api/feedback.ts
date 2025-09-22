import { api } from "./client";
import { API } from "./endpoints";

export type FeedbackPayload = {
  session_id: string;
  rating?: number;               // 1..5
  perceived_notes?: string[];    // ["floral","chocolate"]
  comments?: string;
};

function okish(x: any) {
  if (x == null) return true;
  if (typeof x.ok === "boolean") return x.ok;
  if (typeof x.status === "string") return /^(ok|success)$/i.test(x.status);
  return true;
}

export async function sendFeedback(body: FeedbackPayload): Promise<{ ok: boolean }> {
  try {
    const res = await api.post<unknown>(API.feedback(), body);
    return { ok: okish(res) };
  } catch {
    const res = await api.post<unknown>(API.feedback(), { data: body });
    return { ok: okish(res) };
  }
}
