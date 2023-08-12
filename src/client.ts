import { Chessground } from 'chessground';
import { Api as CgApi } from 'chessground/api';

import { Result } from '@badrap/result';

import { Color, Role, Move, SquareName } from 'chessops/types';
import { parseSquare, parseUci } from 'chessops/util';
import { SquareSet } from 'chessops/squareSet';
import { Setup, MaterialSide } from 'chessops/setup';
import { Chess } from 'chessops/chess';
import { FenError, InvalidFen, makeFen, makeBoardFen, makePocket, parseFen, parseBoardFen } from 'chessops/fen';
import { transformSetup, flipVertical, flipHorizontal } from 'chessops/transform';
import { chessgroundDests, chessgroundMove } from 'chessops/compat';

const DEFAULT_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';

class Controller {
  private events: Record<string, Array<(...args: any) => void> | undefined> = {};

  public setup: Setup = parseFen(DEFAULT_FEN).unwrap();
  public lastMove?: Move;

  private flipped = false;
  public editMode = false;

  constructor(fen: string) {
    parseFen(fen).map(setup => this.setPosition(setup));

    window.addEventListener('popstate', event => {
      const fen = event.state?.fen || new URLSearchParams(location.search).get('fen');
      const setup = (fen ? Result.ok(fen) : Result.err(new FenError(InvalidFen.Fen)))
        .chain(fen => parseFen(fen.replace(/_/g, ' ')))
        .unwrap(
          setup => setup,
          _ => parseFen(DEFAULT_FEN).unwrap(),
        );
      this.setPosition(setup, event.state?.lastMove);
    });
  }

  bind(event: string, cb: (...args: any) => void) {
    this.events[event] = [...(this.events[event] || []), cb];
  }

  trigger(event: string, ...args: any) {
    for (const cb of this.events[event] || []) cb.apply(this, args);
  }

  toggleFlipped() {
    this.flipped = !this.flipped;
    this.trigger('flipped', this.flipped);
  }

  toggleEditMode() {
    this.editMode = !this.editMode;
    this.trigger('editMode', this.editMode);
  }

  push(setup: Setup, lastMove?: Move) {
    if (this.setPosition(setup, lastMove) && 'pushState' in history) {
      const fen = makeFen(this.setup);
      history.pushState(
        {
          fen,
          lastMove,
        },
        '',
        '/?fen=' + fen.replace(/\s/g, '_'),
      );
    }
  }

  pushMove(move: Move) {
    return Chess.fromSetup(this.setup, { ignoreImpossibleCheck: true }).unwrap(
      pos => {
        if (!pos.isLegal(move)) return false;
        pos.play(move);
        this.push(pos.toSetup(), move);
        return true;
      },
      _ => false,
    );
  }

  private setPosition(setup: Setup, lastMove?: Move) {
    if (makeFen(setup) === makeFen(this.setup)) return false;
    this.setup = {
      ...setup,
      halfmoves: 0,
      fullmoves: 1,
    };
    this.lastMove = lastMove;
    this.trigger('setupChanged', this.setup);
    return true;
  }
}

class BoardView {
  private ground: CgApi;

  constructor(private controller: Controller) {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    const ground = (this.ground = Chessground(document.getElementById('board')!, {
      fen: makeBoardFen(controller.setup.board),
      autoCastle: false,
      trustAllEvents: true,
      movable: {
        free: true,
        color: 'both',
        showDests: true,
      },
      selectable: {
        enabled: false,
      },
      draggable: {
        deleteOnDropOff: true,
      },
      animation: {
        enabled: !reducedMotion.matches,
      },
      drawable: {
        defaultSnapToValidMove: false,
      },
      events: {
        move: (orig, dest) => {
          // If the change is a legal move, play it.
          if (!controller.editMode)
            controller.pushMove({
              from: parseSquare(orig)!,
              to: parseSquare(dest)!,
            });
        },
        dropNewPiece: (piece, key) => {
          // Move the existing king, even when dropping a new one.
          if (piece.role !== 'king') return;
          const diff = new Map();
          for (const [k, p] of ground.state.pieces) {
            if (p.role === 'king' && p.color === piece.color) diff.set(k, undefined);
          }
          diff.set(key, piece);
          ground.setPieces(diff);
        },
        change: () => {
          // Otherwise just change to position.
          controller.push({
            ...controller.setup,
            board: parseBoardFen(this.ground.getFen()).unwrap(),
          });
        },
      },
    }));

    for (const el of document.querySelectorAll('.spare piece')) {
      for (const eventName of ['touchstart', 'mousedown']) {
        el.addEventListener(
          eventName,
          e => {
            e.preventDefault();
            const target = e.target as HTMLElement;
            ground.dragNewPiece(
              {
                color: target.getAttribute('data-color') as Color,
                role: target.getAttribute('data-role') as Role,
              },
              e,
              true,
            );
          },
          { passive: false },
        );
      }
    }

    this.setPosition(controller.setup);
    controller.bind('setupChanged', (setup: Setup) => this.setPosition(setup));

    controller.bind('flipped', (flipped: boolean) => this.setFlipped(flipped));

    controller.bind('editMode', (editMode: boolean) => {
      ground.set({
        movable: {
          showDests: !editMode,
        },
      });
    });

    // Change listeners not supported in Safari.
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    reducedMotion.addEventListener?.('change', () => {
      ground.set({
        animation: {
          enabled: !reducedMotion.matches,
        },
      });
    });
  }

  private setPosition(setup: Setup) {
    const pos = Chess.fromSetup(setup, { ignoreImpossibleCheck: true });
    this.ground.set({
      lastMove: this.controller.lastMove && chessgroundMove(this.controller.lastMove),
      fen: makeBoardFen(setup.board),
      turnColor: setup.turn,
      check: pos.unwrap(
        p => p.isCheck() && p.turn,
        _ => false,
      ),
      movable: {
        dests: pos.unwrap(chessgroundDests, _ => undefined),
      },
    });
  }

  private setFlipped(flipped: boolean) {
    const other = flipped ? 'white' : 'black';
    if (other === this.ground.state.orientation) this.ground.toggleOrientation();
    for (const el of document.querySelectorAll('.spare.bottom piece')) {
      el.setAttribute('data-color', this.ground.state.orientation);
      el.classList.toggle('white', this.ground.state.orientation === 'white');
      el.classList.toggle('black', this.ground.state.orientation === 'black');
    }
    for (const el of document.querySelectorAll('.spare.top piece')) {
      el.setAttribute('data-color', other);
      el.classList.toggle('white', other === 'white');
      el.classList.toggle('black', other === 'black');
    }
  }

  unsetHovering() {
    this.ground.setAutoShapes([]);
  }

  setHovering(uci: string) {
    this.ground.setAutoShapes([
      {
        orig: uci.substr(0, 2) as SquareName,
        dest: uci.substr(2, 2) as SquareName,
        brush: 'green',
      },
    ]);
  }
}

class SideToMoveView {
  constructor(controller: Controller) {
    document.getElementById('btn-white')!.addEventListener('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        turn: 'white',
      });
    });

    document.getElementById('btn-black')!.addEventListener('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        turn: 'black',
      });
    });

    this.setPosition(controller.setup);
    controller.bind('setupChanged', (setup: Setup) => this.setPosition(setup));
  }

  private setPosition(setup: Setup) {
    document.getElementById('btn-white')!.classList.toggle('active', setup.turn === 'white');
    document.getElementById('btn-black')!.classList.toggle('active', setup.turn === 'black');
  }
}

class FenInputView {
  constructor(controller: Controller) {
    function relaxedParseFen(fen: string) {
      fen = fen.trim().replace(/_/g, ' ');
      return parseFen(fen || DEFAULT_FEN);
    }

    const input = document.getElementById('fen') as HTMLInputElement;
    input.oninput = input.onchange = () => {
      input.setCustomValidity(
        relaxedParseFen(input.value).unwrap(
          _ => '',
          _ => 'Invalid FEN',
        ),
      );
    };

    document.getElementById('form-set-fen')!.addEventListener('submit', event => {
      event.preventDefault();
      relaxedParseFen(input.value).map(setup => controller.push(setup));
    });

    this.setPosition(controller.setup);
    controller.bind('setupChanged', (setup: Setup) => this.setPosition(setup));
  }

  private setPosition(setup: Setup) {
    const fen = makeFen(setup);
    (document.getElementById('fen') as HTMLInputElement).value = fen === DEFAULT_FEN ? '' : fen;
  }
}

class ToolBarView {
  constructor(controller: Controller) {
    document.getElementById('btn-flip-board')!.addEventListener('click', () => controller.toggleFlipped());
    controller.bind('flipped', (flipped: boolean) =>
      document.getElementById('btn-flip-board')!.classList.toggle('active', flipped),
    );

    document.getElementById('btn-clear-board')!.addEventListener('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        board: parseFen(DEFAULT_FEN).unwrap().board,
        unmovedRooks: SquareSet.empty(),
        epSquare: undefined,
      });
    });

    document.getElementById('btn-swap-colors')!.addEventListener('click', event => {
      event.preventDefault();

      const board = controller.setup.board.clone();
      const white = board.white;
      board.white = board.black;
      board.black = white;

      controller.push({
        ...controller.setup,
        board,
        unmovedRooks: SquareSet.empty(),
        epSquare: undefined,
      });
    });

    document.getElementById('btn-mirror-horizontal')!.addEventListener('click', event => {
      event.preventDefault();
      controller.push(transformSetup(controller.setup, flipHorizontal));
    });

    document.getElementById('btn-mirror-vertical')!.addEventListener('click', event => {
      event.preventDefault();
      controller.push(transformSetup(controller.setup, flipVertical));
    });

    document.getElementById('btn-edit')!.addEventListener('click', () => controller.toggleEditMode());

    controller.bind('editMode', (editMode: boolean) => {
      const btn = document.getElementById('btn-edit')!;
      btn.classList.toggle('active', editMode);
      const icon = btn.querySelector('span.icon')!;
      icon.classList.toggle('icon-lock', editMode);
      icon.classList.toggle('icon-lock-open', !editMode);
    });
  }
}

class TablebaseView {
  abortController: AbortController | null = null;

  constructor(
    controller: Controller,
    private boardView: BoardView,
  ) {
    this.bindMoveLinks();

    controller.bind('setupChanged', (setup: Setup) => {
      if (this.abortController) this.abortController.abort();
      this.abortController = new AbortController();

      const spinner = '<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>';
      const content = document.querySelector('.right-side > .inner')!;
      content.innerHTML = spinner;

      const url = new URL('/', location.href);
      url.searchParams.set('fen', makeFen(setup));
      url.searchParams.set('xhr', 'probe');

      fetch(url.href, {
        signal: this.abortController.signal,
      })
        .then(res => {
          if (res.ok) return res.text();
          else throw res;
        })
        .then(html => {
          content.innerHTML = html;
          this.bindMoveLinks();
        })
        .catch(err => {
          content.innerHTML = `<section><h2 id="status">Network error ${err.status || 0}</h2><div id="info">${
            err.statusText || ''
          }</div></section>`;
        })
        .finally(() => {
          this.abortController = null;
        });
    });
  }

  private bindMoveLinks() {
    const boardView = this.boardView;
    for (const el of document.querySelectorAll('a.li')) {
      el.addEventListener('click', function (this: HTMLElement, event: MouseEvent) {
        event.preventDefault();
        controller.pushMove(parseUci(this.getAttribute('data-uci')!)!);
        boardView.unsetHovering();
      });
      el.addEventListener('mouseover', function (this: HTMLElement) {
        boardView.setHovering(this.getAttribute('data-uci')!);
      });
      el.addEventListener('mouseleave', () => boardView.unsetHovering());
    }
  }
}

class DocumentTitle {
  constructor(controller: Controller) {
    controller.bind('setupChanged', (setup: Setup) => {
      const side = (color: Color) =>
        makePocket(MaterialSide.fromBoard(setup.board, color)).split('').reverse().join('').toUpperCase();
      document.title = `${side('white')}v${side('black')} – Syzygy endgame tablebases`;
    });
  }
}

const controller = new Controller(document.getElementById('board')!.getAttribute('data-fen')!);

const boardView = new BoardView(controller);
new SideToMoveView(controller);
new FenInputView(controller);
new ToolBarView(controller);

new DocumentTitle(controller);
new TablebaseView(controller, boardView);

console.log('syzygy-tables.info is free/libre open source software! https://github.com/niklasf/syzygy-tables.info');
