"""ARC H - the door onto the vector index: it says what it HOLDS, and it never creates a lie.

``make qdrant`` and ``make qdrant-up`` make the vector service state observable and actionable.

What these tests defend is subtler than "the commands exist". A vector index has a failure mode with
no symptom: an EMPTY server answers exactly like a full one, the search simply admits "no confident
memory" (invariant 14), and the reader believes the library holds nothing.

**The first version of these tests was audited and came back NON SOUTENABLE**, and the findings are
worth keeping in front of whoever edits this file, because every one of them is a way of testing the
WORDS instead of the BEHAVIOUR:

* a server answering HTTP 500 (or 403 "API key required") produced the same empty tuple as a dead
  one, and the status then printed a confident "holds NOTHING" over a live collection -
  **and a test pinned that conflation**, so sabotaging it was "caught" while the lie shipped;
* ``make qdrant-up``'s central promise - *it never creates a container* - was asserted only on the
  TEXT of the refusal, so a version that cheerfully created one passed every test;
* the assertion labelled "the total" was satisfied by a per-collection line, so forcing the total to
  zero changed nothing that any test could see;
* a stopped Docker daemon (exit 1, like a missing container) rendered "ABSENT from this machine" and
  handed operator a ``docker run`` command while his index sat intact behind a daemon nobody could ask.

Brick-free (stdlib only, D126).

Translation note for this public mirror: ``mnemosyne.runtime.qdrant_run`` now prints its
operator-facing lines in English, so the assertions below check the EXACT English strings it
emits ("NOTHING ANSWERS", "ABSENT from this machine", "was already running", etc.) rather than
the French wording an earlier version of this file pinned. Only string literals were touched to
keep the assertions matched to the real output; identifiers, imports, and numbers are untouched.
"""

from __future__ import annotations

from collections.abc import Sequence

from mnemosyne.runtime.qdrant_run import (
    CREATE_COMMAND,
    QDRANT_CONTAINER,
    Collection,
    ContainerFacts,
    Inventory,
    QdrantState,
    read_collections,
    read_container,
    cmd_demarrer,
    render_start,
    render_state,
    start_container,
)

_UP = ContainerFacts(
    known=True, exists=True, running=True, restart_policy="unless-stopped", mounts=1
)
_FULL = Inventory(known=True, collections=(Collection("mnemosyne_public", 240498),))


def _state(*, listening=True, inventory=_FULL, container=_UP) -> QdrantState:
    return QdrantState(
        url="http://localhost:6333", listening=listening, inventory=inventory, container=container
    )


def _docker(
    code: int = 0, out: str = "", err: str = "", *, start: tuple[int, str, str] | None = None
):
    """A fake docker that RECORDS its argv - the only way to test an abstention.

    ``start`` answers the ``start`` subcommand separately: a single answer for every subcommand made
    "inspect failed" and "start failed" indistinguishable, so a test aimed at one measured the other.
    """
    seen: list[tuple[str, ...]] = []

    def run(args: Sequence[str]) -> tuple[int, str, str]:
        seen.append(tuple(args))
        if start is not None and args and args[0] == "start":
            return start
        return (code, out, err)

    return run, seen


# ====================================================================================== #
# "I could not read it" is NEVER "it holds nothing" - the class this whole door exists for #
# ====================================================================================== #


def test_an_answering_server_whose_inventory_cannot_be_read_says_exactly_that() -> None:
    # The dangerous middle case, and the one that shipped: it answers, but not with an inventory we
    # can parse. "0 passage" here is a confident lie about a library that may be entirely intact.
    out = render_state(_state(inventory=Inventory(known=False)))
    assert "I COULD NOT READ ITS INVENTORY" in out
    assert '**not** "it is empty"' in out
    assert "0 passages" not in out and "NO COLLECTION AT ALL" not in out


def test_an_http_error_is_unknown_not_empty() -> None:
    # HTTPError subclasses URLError, which is how a 500 and a refused connection became the same
    # thing. Both branches are asserted here, because they must lead to OPPOSITE messages.
    import urllib.error

    def five_hundred(url: str) -> dict:
        raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None)  # type: ignore[arg-type]

    def forbidden(url: str) -> dict:
        raise urllib.error.HTTPError(url, 403, "Forbidden: API key required", {}, None)  # type: ignore[arg-type]

    def unexpected_shape(url: str) -> dict:
        return {"result": None}  # a payload that is not the shape we expect: AttributeError bait

    for failing in (five_hundred, forbidden, unexpected_shape):
        inventory = read_collections("http://localhost:6333", get=failing)
        assert inventory.known is False, failing.__name__
        assert inventory.collections == ()


def test_a_genuinely_empty_server_is_still_called_out() -> None:
    # The other polarity: "known and empty" must NOT be softened into "unknown". A fresh container is
    # healthy, accepts queries, holds nothing - and that is exactly what must be shouted.
    out = render_state(_state(inventory=Inventory(known=True, collections=())))
    assert "NO COLLECTION AT ALL" in out
    assert "answers just like a full one" in out


def test_a_configured_index_reports_its_contents_not_merely_that_it_answers() -> None:
    out = render_state(
        _state(
            inventory=Inventory(
                known=True,
                collections=(
                    Collection("public_example", 125),
                    Collection("restricted_example", 8),
                    Collection("empty_example", 0),
                ),
            )
        )
    )
    # TWO non-zero readable counts, deliberately: with a single one, `sum` and `max` are
    # indistinguishable, and an audit swapped one for the other with the whole suite green - the
    # word "total" was never tested. The assertion is on the WHOLE line (it used to be a prefix,
    # so a corrupted caveat appended after it slipped through).
    assert "   total read: 133 passages" in out.splitlines()
    assert "public_example — 125 passages" in out
    assert "\U000026A0\U0000FE0F EMPTY" in out  # the empty partition is NAMED, not silently summed away
    assert "   · 3 collection(s) read" not in out  # (guard against a stale count line shape)
    assert "\U00002705 answers — 3 collection(s)" in out  # the COUNT itself, held by nothing before


def test_the_total_never_counts_an_unreadable_collection_as_zero() -> None:
    # Measured on the shipped version: every count unreadable rendered "0 passage(s) au total" on the
    # line meant to be read at a glance, while the detail said "illisible". On this door the glance
    # IS the reading. An unknown count is excluded from the total AND declared.
    inventory = Inventory(
        known=True, collections=(Collection("mnemosyne_public", -1), Collection("other", 7))
    )
    assert inventory.readable_total == 7 and inventory.unreadable == 1
    out = render_state(_state(inventory=inventory))
    assert (
        "   total read: 7 passages (+ 1 collection(s) with an UNREADABLE count, not counted)"
        in out.splitlines()
    )
    # and a collection that is genuinely EMPTY is not smuggled into the "unreadable" tally: the two
    # words mean opposite things, and a `<= 0` there passed the whole suite.
    both = Inventory(
        known=True, collections=(Collection("a", -1), Collection("b", 0), Collection("c", 5))
    )
    assert both.unreadable == 1 and both.readable_total == 5
    assert "unreadable count" in out
    assert "EMPTY" not in out  # unknown is NOT zero


def test_a_dead_index_names_the_gesture_that_revives_it() -> None:
    out = render_state(_state(listening=False))
    assert "NOTHING ANSWERS" in out
    assert (
        "make qdrant-up" in out
    )  # a gesture operator can type; a diagnosis he cannot act on is noise


# ====================================================================================== #
# The two facts that explain WHY it keeps dying, printed where someone is looking at it   #
# ====================================================================================== #


def test_the_status_says_it_will_not_survive_a_reboot_when_it_will_not() -> None:
    fragile = ContainerFacts(known=True, exists=True, running=True, restart_policy="no", mounts=1)
    out = render_state(_state(container=fragile))
    assert "does NOT come back" in out and "docker update --restart unless-stopped" in out
    assert "does NOT come back" not in render_state(
        _state(container=_UP)
    )  # quiet when the policy is sound
    # A policy Docker did not report is NOT a durable one. `!= "no"` passed the entire suite because
    # no fixture ever carried an empty policy - the branch `_render_container` has for it was unjudged.
    silent = ContainerFacts(known=True, exists=True, running=True, restart_policy="", mounts=1)
    assert silent.survives_reboot is False
    assert "does NOT come back" in render_state(_state(container=silent))


def test_the_status_warns_that_removing_the_container_would_destroy_the_index() -> None:
    naked = ContainerFacts(known=True, exists=True, running=True, restart_policy="always", mounts=0)
    out = render_state(_state(container=naked))
    assert "NO VOLUME AT ALL" in out and f"docker rm {QDRANT_CONTAINER}" in out
    assert "D56" in out  # ... and stays honest: a rebuildable derivative, not lost truth
    assert "NO VOLUME AT ALL" not in render_state(_state(container=_UP))


def test_a_docker_we_could_not_ask_never_reads_as_a_container_that_does_not_exist() -> None:
    # "We could not ask" and "it does not exist" lead to opposite gestures - one says start Docker,
    # the other hands over a `docker run` that would create a SECOND, empty container beside a full
    # one. Both the missing CLI and the dead daemon must land on "unknown".
    absent_cli = read_container(run=_docker(127, "", "docker introuvable")[0])
    dead_daemon = read_container(
        run=_docker(1, "", "Cannot connect to the Docker daemon at unix:///var/run/docker.sock.")[0]
    )
    for facts in (absent_cli, dead_daemon):
        assert facts.known is False and facts.exists is False
        out = render_state(_state(container=facts))
        assert "I could NOT ask Docker" in out
        assert "ABSENT" not in out and CREATE_COMMAND not in out


def test_only_no_such_object_proves_a_container_is_absent() -> None:
    # Enumerating what PROVES absence, rather than blacklisting the failures we happened to meet.
    absent = read_container(run=_docker(1, "", "Error: No such object: mnemo-qdrant")[0])
    assert absent.known is True and absent.exists is False
    assert "ABSENT from this machine" in render_state(_state(container=absent))

    puzzling = read_container(run=_docker(1, "", "permission denied while trying to connect")[0])
    assert puzzling.known is False  # an unrecognised error is NOT a confident absence


def test_docker_facts_are_parsed_from_the_single_inspect_call() -> None:
    facts = read_container(run=_docker(0, "true|unless-stopped|2")[0])
    assert facts.known and facts.exists and facts.running
    assert facts.restart_policy == "unless-stopped" and facts.mounts == 2 and facts.survives_reboot


# ====================================================================================== #
# `make qdrant-up` starts what exists - and the ABSTENTION is what is tested              #
# ====================================================================================== #


def test_the_start_gesture_never_creates_a_container_whatever_docker_says() -> None:
    # THE guarantee of H2, and the audit found it asserted only on the wording of the refusal: a
    # version that created a container passed the whole suite. What is checked now is the argv Docker
    # actually receives. A fresh container is empty and, from outside, identical to the real one.
    for code, out, err in (
        (1, "", "Error: No such object: mnemo-qdrant"),  # absent
        (127, "", "docker introuvable"),  # no docker at all
        (0, "false|no|0", ""),  # present but stopped
        (0, "true|no|0", ""),  # already running
    ):
        run, seen = _docker(code, out, err)
        start_container(run=run)
        forbidden = [argv for argv in seen if {"run", "create", "rm", "stop"} & set(argv)]
        assert not forbidden, f"qdrant-up attempted a forbidden gesture: {forbidden}"


def test_the_start_gesture_starts_a_stopped_container_and_only_a_stopped_one() -> None:
    run, seen = _docker(0, "false|no|0")
    facts, started = start_container(run=run)
    assert started is True and ("start", QDRANT_CONTAINER) in seen

    run, seen = _docker(0, "true|no|0")  # already running -> no second start
    facts, started = start_container(run=run)
    assert started is False and not [argv for argv in seen if "start" in argv]
    assert "was already running" in render_start(facts, started=False)


def test_the_refusal_to_create_says_why_and_prints_the_command_it_will_not_run() -> None:
    out = render_start(ContainerFacts(known=True, exists=False), started=False)
    assert "does not exist" in out and "I do NOT create it" in out
    assert "no trusted memory" in out  # names the failure mode, not just the policy
    assert CREATE_COMMAND in out


def test_an_unreachable_docker_never_hands_over_the_creation_command() -> None:
    # Closed for `render_state`, left open for `render_start`: no test ever called it with
    # `known=False`, so a mutation made the START gesture print "does not exist" + `docker run`
    # while the index sat intact behind a daemon nobody could ask. Word for word the defect this
    # file's header declares fixed - fixed on one of the two renderers.
    out = render_start(ContainerFacts(known=False, why_unknown="daemon down"), started=False)
    assert "Docker is unreachable" in out
    assert CREATE_COMMAND not in out and "does not exist" not in out


def test_the_printed_creation_command_fixes_both_defects_of_the_one_we_have() -> None:
    assert "--restart unless-stopped" in CREATE_COMMAND
    assert "-v " in CREATE_COMMAND and ":/qdrant/storage" in CREATE_COMMAND
    assert QDRANT_CONTAINER in CREATE_COMMAND


def test_a_container_that_refuses_to_start_is_reported_as_a_failure() -> None:
    stopped = ContainerFacts(known=True, exists=True, running=False, restart_policy="no", mounts=0)
    assert "refused to start" in render_start(stopped, started=False)
    assert "is back up" in render_start(stopped, started=True)


# ====================================================================================== #
# Reading the world: tolerant, and never confidently wrong                                #
# ====================================================================================== #


def test_a_single_unreadable_collection_is_kept_and_marked_not_dropped() -> None:
    def flaky(url: str) -> dict:
        if url.endswith("/collections"):
            return {"result": {"collections": [{"name": "b"}, {"name": "a"}]}}
        if url.endswith("/a"):
            return {"result": {"points_count": 7}}
        raise OSError("collection detail unavailable")

    inventory = read_collections("http://localhost:6333", get=flaky)
    assert inventory.known is True  # the LISTING was readable - that part we do know
    assert [(c.name, c.points) for c in inventory.collections] == [("a", 7), ("b", -1)]


def test_the_deadline_is_read_off_a_clock_not_summed_from_the_sleeps() -> None:
    # `docker start` returns 0 the moment the order is accepted, and docker-proxy binds the port at
    # once - so " it is back" was printed seconds before Qdrant could answer. The wait closes that.
    #
    # But the FIRST version of this test proved nothing: it injected a cost-free probe, so it only
    # ever measured the sleeps it had itself supplied. An audit then measured the real function
    # overshooting its announced bound by 5-6× (~100 s for a declared 20 s), because each probe
    # BLOCKS for up to its own timeout against a held-but-mute port - the only state this function
    # exists for. Here the fake clock advances on the probe as well as on the sleep.
    from mnemosyne.runtime.qdrant_run import wait_until_ready

    clock = [0.0]
    probes = [0]

    def now() -> float:
        return clock[0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    def costly_and_mute(url: str) -> bool:
        probes[0] += 1
        clock[0] += 1.0  # what a real probe costs against a port that never answers
        return False

    assert (
        wait_until_ready("http://x", deadline=5.0, ready=costly_and_mute, sleep=sleep, now=now)
        is False
    )
    assert clock[0] <= 5.0 + 1.0 + 0.25, f"announced bound 5 s, actual time {clock[0]} s"
    assert probes[0] >= 2  # ... and it really did poll, it did not give up on the first look


def test_the_wait_returns_as_soon_as_the_service_answers() -> None:
    from mnemosyne.runtime.qdrant_run import wait_until_ready

    clock = [0.0]
    slow = iter([False, False, True])
    assert (
        wait_until_ready(
            "http://x",
            ready=lambda url: next(slow),
            sleep=lambda s: clock.__setitem__(0, clock[0] + s),
            now=lambda: clock[0],
        )
        is True
    )
    assert clock[0] == 0.5  # two polls, two steps - no fixed block of waiting


def test_a_container_that_restarted_but_stays_mute_is_not_announced_as_back() -> None:
    stopped = ContainerFacts(known=True, exists=True, running=False, restart_policy="no", mounts=1)
    mute = render_start(stopped, started=True, ready=False)
    assert "NOT ANSWERING" in mute and "docker logs" in mute
    assert "\U00002705" not in mute
    assert "is back up AND it answers" in render_start(stopped, started=True, ready=True)


def test_an_already_running_container_is_only_blessed_once_it_ANSWERS() -> None:
    # The likeliest branch of all - a second `make qdrant-up`, or Docker Desktop restarting the
    # container - used to print " was already running" without ever asking whether it answers, so the
    # promise in the commit title was untrue exactly where it mattered most. And one of my own tests
    # pinned that: the same shape as the audited defect where a test froze the confusion it should
    # have caught.
    mute = render_start(_UP, started=False, ready=False)
    assert "was already running, but it is NOT ANSWERING" in mute and "\U00002705" not in mute
    assert "was already running AND it answers" in render_start(_UP, started=False, ready=True)


def test_readiness_is_tri_state_a_question_never_asked_is_not_a_failure() -> None:
    # Nothing was started, so readiness was never asked. Printing "not ready" here would be the same
    # conflation between "unknown" and "no" that this module fights everywhere else.
    already = render_start(_UP, started=False, ready=None)
    assert "was already running" in already and "NOT ANSWERING" not in already


# ====================================================================================== #
# The CLI itself - the layer that had no test at all, and where three sabotages survived  #
# ====================================================================================== #


def test_the_status_judges_a_port_exactly_as_the_start_does() -> None:
    # An audit found the two diverged: the preflight required an HTTP answer while this door was
    # content with a held port, so `make qdrant` announced "IT ANSWERS" about docker-proxy and then
    # blamed "a proxy in front" - pointing the reader away from the truth ("nothing answers yet").
    import socket
    import threading

    from mnemosyne.runtime.qdrant_run import read_state

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    held: list[socket.socket] = []

    def accept_and_say_nothing() -> None:
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            held.append(connection)

    threading.Thread(target=accept_and_say_nothing, daemon=True).start()
    try:
        state = read_state(f"http://127.0.0.1:{port}", run=_docker(127, "", "no docker")[0])
        assert state.listening is False, "the status blesses a merely-held port"
        assert "NOTHING ANSWERS" in render_state(state)
    finally:
        listener.close()
        for connection in held:
            connection.close()


def test_the_status_exit_code_says_failure_when_it_cannot_see_the_library() -> None:
    # A status that exits 0 while unable to see the index reads as success to every script and every
    # reader. Three sabotages on these two functions survived the entire suite before this test.
    import io

    from mnemosyne.runtime.qdrant_run import cmd_etat

    def state(**kw) -> QdrantState:
        return _state(**kw)

    assert cmd_etat("http://x", state=state(), out=io.StringIO()) == 0
    assert cmd_etat("http://x", state=state(listening=False), out=io.StringIO()) == 1
    assert (
        cmd_etat("http://x", state=state(inventory=Inventory(known=False)), out=io.StringIO()) == 1
    )


def test_the_start_command_reports_failure_when_the_service_stays_mute() -> None:
    import io

    from mnemosyne.runtime.qdrant_run import cmd_demarrer

    run, _ = _docker(0, "false|no|0")  # exists, stopped -> gets started
    assert (
        cmd_demarrer("http://x", run=run, ready=lambda url: True, deadline=0.0, out=io.StringIO())
        == 0
    )
    run, _ = _docker(0, "false|no|0")
    assert (
        cmd_demarrer("http://x", run=run, ready=lambda url: False, deadline=0.0, out=io.StringIO())
        == 1
    )

    run, _ = _docker(1, "", "Error: No such object: mnemo-qdrant")  # absent -> refusal, never 0
    assert (
        cmd_demarrer("http://x", run=run, ready=lambda url: True, deadline=0.0, out=io.StringIO())
        == 1
    )


def test_reading_the_api_is_really_bounded_in_time_and_stays_on_the_machine() -> None:
    # The version this replaces was a `grep`: `assert "timeout=_HTTP_TIMEOUT" in source`. Moving that
    # literal INTO A COMMENT satisfied it while `make qdrant` became unbounded - measured blocked
    # past 12 s against a held-but-mute port, which is exactly `docker-proxy` and exactly the
    # 30-minute sleep this whole module exists to close. A name is not a test: MEASURE the time.
    import socket
    import threading
    import time

    from mnemosyne.runtime.qdrant_run import _HTTP_TIMEOUT, _http_get_json

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    held: list[socket.socket] = []

    def accept_and_say_nothing() -> None:
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            held.append(connection)

    threading.Thread(target=accept_and_say_nothing, daemon=True).start()

    # The call runs in a bounded thread, and that is not ceremony: measuring the elapsed time AFTER
    # the call means the assertion is never reached when the call never returns - the suite HANGS
    # instead of going red, in the module whose whole purpose is to close hangs. A test must fail,
    # not stall. (Daemon thread, so a stuck one cannot hold pytest either.)
    elapsed: list[float] = []

    def read_it() -> None:
        began = time.monotonic()
        try:
            _http_get_json(f"http://127.0.0.1:{port}/collections")
        except Exception:  # noqa: BLE001 - what matters is that it RETURNS, whatever it raises
            pass
        elapsed.append(time.monotonic() - began)

    worker = threading.Thread(target=read_it, daemon=True)
    worker.start()
    worker.join(timeout=_HTTP_TIMEOUT + 3.0)
    alive = worker.is_alive()
    listener.close()
    for connection in held:
        connection.close()
    assert not alive, "the API read NEVER returns control: it is not bounded"
    assert elapsed[0] <= _HTTP_TIMEOUT + 1.0, f"the API read took {elapsed[0]:.1f} s"


def test_reading_the_api_cannot_leave_the_machine_either() -> None:
    # Same incapacity as the readiness probe, on the other HTTP caller. It was held by a comment
    # only: rewriting it with `urlopen` kept the literal, passed the suite, and followed a 302 off
    # the machine. Whatever holds port 6333 must not be able to redirect a status command anywhere.
    import http.server
    import threading

    from mnemosyne.runtime.local_first import watch_outbound_network
    from mnemosyne.runtime.qdrant_run import _http_get_json

    class Redirecting(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            self.send_response(302)
            self.send_header("Location", "http://qdrant-mirror.example.com/")
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirecting)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with watch_outbound_network(refuse=True) as attempts:
            try:
                _http_get_json(f"http://127.0.0.1:{server.server_port}/collections")
            except Exception:  # noqa: BLE001 - a 302 is not JSON; what matters is where it went
                pass
        assert attempts == [], f"the API read left the machine: {attempts}"
    finally:
        server.shutdown()
        server.server_close()


def test_the_status_really_reads_the_inventory_and_really_prints_it() -> None:
    # Two wirings that no assertion held: `read_state` could stop calling `read_collections` (the
    # door would then ALWAYS say "I could not read it"), and `cmd_etat` could print nothing at all -
    # the three exit-code assertions passed an `out` buffer and never read it back. The whole point
    # of this door is what it PRINTS.
    import io

    from mnemosyne.runtime.qdrant_run import cmd_etat

    printed = io.StringIO()
    code = cmd_etat("http://x", state=_state(), out=printed)
    body = printed.getvalue()
    assert code == 0
    assert "passages" in body and "total read" in body, "the door does not print what it holds"
    assert len(body.splitlines()) >= 5


def test_the_status_actually_asks_the_server_what_it_holds() -> None:
    import http.server
    import threading

    from mnemosyne.runtime.qdrant_run import read_state

    asked: list[str] = []

    class Serving(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            asked.append(self.path)
            body = (
                b'{"result": {"collections": [{"name": "mnemosyne_public"}]}}'
                if self.path.endswith("/collections")
                else b'{"result": {"points_count": 42}}'
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Serving)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        state = read_state(
            f"http://127.0.0.1:{server.server_port}", run=_docker(127, "", "no docker")[0]
        )
        assert state.listening is True
        assert state.inventory.known is True, "read_state no longer reads the inventory at all"
        assert [(c.name, c.points) for c in state.inventory.collections] == [
            ("mnemosyne_public", 42)
        ]
        assert any(path.endswith("/collections") for path in asked)
    finally:
        server.shutdown()
        server.server_close()


def test_the_start_command_really_asks_readiness_on_the_already_running_branch() -> None:
    # The likeliest branch of all, and its WIRING was held by nothing: `render_start` was tested
    # directly, so dropping `or (facts.known and facts.running)` printed " was already running
    # AND it answers" about a mute service, with the entire suite green - the exact promise of the commit.
    import io

    for out, label in (("true|no|0", "already running"), ("false|no|0", "stopped then relaunched")):
        asked: list[str] = []
        run, _ = _docker(0, out)
        code = cmd_demarrer(
            "http://x",
            run=run,
            ready=lambda url: asked.append(url) or False,
            deadline=0.0,
            out=io.StringIO(),
        )
        assert asked, f"readiness never asked on the '{label}' branch"
        assert code == 1


def test_the_start_command_believes_docker_when_it_says_the_start_failed() -> None:
    # `[0] == 0` and `True` were indistinguishable: every fixture returned code 0, so ignoring the
    # exit code turned a failed start into a false "" restart report. And the test that claimed
    # to cover the failure fabricated its own `started=False` instead of measuring it.
    import io

    from mnemosyne.runtime.qdrant_run import start_container

    facts, started = start_container(run=_docker(0, "false|no|0")[0])
    assert started is True
    printed = io.StringIO()
    refusing, _ = _docker(
        0, "false|no|0", start=(1, "", "Error response from daemon: port is allocated")
    )
    code = cmd_demarrer("http://x", run=refusing, ready=lambda url: True, out=printed)
    assert "refused to start" in printed.getvalue() and code == 1
