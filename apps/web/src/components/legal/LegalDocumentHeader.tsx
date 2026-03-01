"use client";

import Image from "next/image";
import Link from "next/link";
import { LEGAL_COMPANY_NAME } from "@/app/legal/_legalMeta";

export default function LegalDocumentHeader() {
  return (
    <header
      className="flex items-center justify-between gap-4 border-b border-zinc-200 pb-4 mb-6"
      style={{ maxWidth: 920, margin: "0 auto 0 auto", padding: "0 16px" }}
    >
      <Link href="/" className="flex-shrink-0 print:pointer-events-none">
        <Image
          src="/Logo_RI_Green_noback.png"
          alt={LEGAL_COMPANY_NAME}
          width={240}
          height={96}
          className="h-20 w-auto object-contain"
        />
      </Link>
      <div className="flex-1 text-center font-semibold text-zinc-800 text-3xl">
        {LEGAL_COMPANY_NAME}
      </div>
      <div className="flex-shrink-0 w-[120px] flex justify-end">
        <button
          type="button"
          onClick={() => window.print()}
          className="print:hidden text-sm px-3 py-2 border border-zinc-300 rounded hover:bg-zinc-100 text-zinc-700"
        >
          Print / Save PDF
        </button>
      </div>
    </header>
  );
}
