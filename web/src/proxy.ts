import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Keep retired franchise/pre-opening surfaces out of the active single-store
 * product without deleting user-owned historical implementation files.
 */
export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  let destination = "/overview";

  if (path.startsWith("/investment")) destination = "/profit";
  else if (path.startsWith("/risks")) destination = "/alerts";
  else if (path === "/operations/delivery") destination = "/channels";
  else if (path === "/operations/daily") destination = "/sales";
  else if (path === "/operations/permissions") destination = "/settings";
  else if (path.startsWith("/operations")) destination = "/dashboard";

  return NextResponse.redirect(new URL(destination, request.url), 308);
}

export const config = {
  matcher: [
    "/investment/:path*",
    "/risks/:path*",
    "/operations/:path*",
    "/overview/actions",
  ],
};
