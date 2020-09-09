/**
 * This file is part of the syzygy-tables.info tablebase probing website.
 * Copyright (C) 2015-2020 Niklas Fiekas <niklas.fiekas@backscattering.de>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import $ from 'cash-dom';
import { Cash } from 'cash-dom';

import { Chessground } from 'chessground';
import { Api as CgApi } from 'chessground/api';

import { Color, Role, Move, SquareName, isDrop } from 'chessops/types';
import { parseSquare, parseUci, makeSquare } from 'chessops/util';
import { SquareSet } from 'chessops/squareSet';
import { Setup } from 'chessops/setup';
import { Chess } from 'chessops/chess';
import { makeFen, makeBoardFen, parseFen, parseBoardFen } from 'chessops/fen';
import { transformSetup, flipVertical, flipHorizontal } from 'chessops/transform';
import { chessgroundDests } from 'chessops/compat';


function chessgroundLastMove(move: Move): SquareName[] {
  if (isDrop(move)) return [makeSquare(move.to)];
  else return [makeSquare(move.from), makeSquare(move.to)];
}


const DEFAULT_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';


class Controller {
  private events: Record<string, Array<(...args: any) => void>> = {};

  public setup: Setup;
  public lastMove?: Move;

  private flipped = false;
  public editMode = false;

  constructor(fen?: string) {
    this.setup = parseFen(DEFAULT_FEN).unwrap();
    if (fen) parseFen(fen).unwrap(setup => this.setPosition(setup), _ => {});

    window.addEventListener('popstate', event => {
      const fen = event.state?.fen || new URLSearchParams(location.search).get('fen') || DEFAULT_FEN;
      this.setPosition(parseFen(fen.replace(/_/g, ' ')).unwrap(
        setup => setup,
        _ => parseFen(DEFAULT_FEN).unwrap()
      ), event.state?.lastMove);
    });
  }

  bind(event: string, cb: (...args: any) => void) {
    this.events[event] = this.events[event] || [];
    this.events[event].push(cb);
  }

  trigger(event: string, ...args: any) {
    if (this.events[event]) for (const cb of this.events[event]) {
      cb.apply(this, args);
    }
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
      history.pushState({
        fen,
        lastMove,
      }, '', '/?fen=' + fen.replace(/\s/g, '_'));
    }
  }

  pushMove(move: Move) {
    return Chess.fromSetup(this.setup).unwrap(pos => {
      if (!pos.isLegal(move)) return false;
      pos.play(move);
      this.push(pos.toSetup(), move);
      return true;
    }, _ => false);
  }

  private setPosition(setup: Setup, lastMove?: Move) {
    if (makeFen(setup) == makeFen(this.setup)) return false;
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

    const ground = this.ground = Chessground(document.getElementById('board')!, {
      fen: makeBoardFen(controller.setup.board),
      autoCastle: false,
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
      events: {
        move: (orig, dest) => {
          // If the change is a legal move, play it.
          if (!controller.editMode) controller.pushMove({
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
    });

    for (const el of document.querySelectorAll('.spare piece')) {
      for (const eventName of ['touchstart', 'mousedown']) {
        el.addEventListener(eventName, e => {
          e.preventDefault();
          const target = e.target as HTMLElement;
          ground.dragNewPiece({
            color: target.getAttribute('data-color') as Color,
            role: target.getAttribute('data-role') as Role,
          }, e, true);
        }, {passive: false});
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

    reducedMotion.addEventListener?.('change', () => {
      ground.set({
        animation: {
          enabled: !reducedMotion.matches,
        },
      });
    });
  }

  private setPosition(setup: Setup) {
    const pos = Chess.fromSetup(setup);
    this.ground.set({
      lastMove: this.controller.lastMove && chessgroundLastMove(this.controller.lastMove),
      fen: makeBoardFen(setup.board),
      turnColor: setup.turn,
      check: pos.unwrap(p => p.isCheck() && p.turn, _ => false),
      movable: {
        dests: pos.unwrap(chessgroundDests, _ => undefined),
      },
    });
  }

  private setFlipped(flipped: boolean) {
    var other = flipped ? 'white' : 'black';
    if (other === this.ground.state.orientation) this.ground.toggleOrientation();
    $('.spare.bottom piece').attr('data-color', this.ground.state.orientation);
    $('.spare.bottom piece').toggleClass('white', this.ground.state.orientation === 'white');
    $('.spare.bottom piece').toggleClass('black', this.ground.state.orientation === 'black');
    $('.spare.top piece').attr('data-color', other);
    $('.spare.top piece').toggleClass('white', other === 'white');
    $('.spare.top piece').toggleClass('black', other === 'black');
  }

  unsetHovering() {
    this.ground.setAutoShapes([]);
  }

  setHovering(uci: string) {
    this.ground.setAutoShapes([{
      orig: uci.substr(0, 2) as SquareName,
      dest: uci.substr(2, 2) as SquareName,
      brush: 'green',
    }]);
  }
}


class SideToMoveView {
  constructor(controller: Controller) {
    $('#btn-white').on('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        turn: 'white',
      });
    });

    $('#btn-black').on('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        turn: 'black',
      })
    });

    this.setPosition(controller.setup);
    controller.bind('setupChanged', (setup: Setup) => this.setPosition(setup));
  }

  private setPosition(setup: Setup) {
    $('#btn-white').toggleClass('active', setup.turn === 'white');
    $('#btn-black').toggleClass('active', setup.turn === 'black');
  }
}


class FenInputView {
  constructor(controller: Controller) {
    function relaxedParseFen(fen: string) {
      fen = fen.trim().replace(/_/g, ' ');
      return parseFen(fen || DEFAULT_FEN);
    }

    const input = document.getElementById('fen') as HTMLInputElement;
    if (input.setCustomValidity) {
      input.oninput = input.onchange = () => {
        input.setCustomValidity(relaxedParseFen(input.value).unwrap(_ => '', _ => 'Invalid FEN'));
      };
    }

    $('#form-set-fen').on('submit', event => {
      event.preventDefault();
      relaxedParseFen(input.value).unwrap(
        setup => controller.push(setup),
        _ => input.setCustomValidity || input.focus()
      );
    });

    this.setPosition(controller.setup);
    controller.bind('setupChanged', (setup: Setup) => this.setPosition(setup));
  }

  private setPosition(setup: Setup) {
    const fen = makeFen(setup);
    $('#fen').val(fen === DEFAULT_FEN ? '' : fen);
  }
}


class ToolBarView {
  constructor(controller: Controller) {
    $('#btn-flip-board').on('click', () => controller.toggleFlipped());
    controller.bind('flipped', (flipped: boolean) => $('#btn-flip-board').toggleClass('active', flipped));

    $('#btn-clear-board').on('click', event => {
      event.preventDefault();
      controller.push({
        ...controller.setup,
        board: parseFen(DEFAULT_FEN).unwrap().board,
        unmovedRooks: SquareSet.empty(),
        epSquare: undefined,
      });
    });

    $('#btn-swap-colors').on('click', event => {
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

    $('#btn-mirror-horizontal').on('click', event => {
      event.preventDefault();
      controller.push(transformSetup(controller.setup, flipHorizontal));
    });

    $('#btn-mirror-vertical').on('click', event => {
      event.preventDefault();
      controller.push(transformSetup(controller.setup, flipVertical));
    });

    $('#btn-edit').on('click', () => controller.toggleEditMode());

    controller.bind('editMode', (editMode: boolean) => {
      $('#btn-edit').toggleClass('active', editMode);
      $('#btn-edit > span.icon')
        .toggleClass('icon-lock', editMode)
        .toggleClass('icon-lock-open', !editMode);
    });
  }
}


class TablebaseView {
  constructor(controller: Controller, boardView: BoardView) {
    function bindMoveLink($moveLink: Cash) {
      $moveLink
        .on('click', function (this: HTMLElement, event: MouseEvent) {
          event.preventDefault();
          controller.pushMove(parseUci($(this).attr('data-uci')!)!);
          boardView.unsetHovering();
        })
        .on('mouseenter', function (this: HTMLElement) {
          boardView.setHovering($(this).attr('data-uci')!);
        })
        .on('mouseleave', () => boardView.unsetHovering());
    }

    bindMoveLink($('a.list-group-item'));

    let abortController: AbortController | null = null;
    controller.bind('setupChanged', (setup: Setup) => {
      if (abortController) abortController.abort();
      abortController = new AbortController();

      const spinner = '<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>';
      const $content = $('.right-side > .inner').html(spinner);

      const url = new URL('/', location.href);
      url.searchParams.set('fen', makeFen(setup));
      url.searchParams.set('xhr', 'probe');

      fetch(url.href, {
        signal: abortController.signal
      }).then(res => {
        if (res.ok) return res.text();
        else throw res;
      }).then(html => {
        $content.html(html);
        bindMoveLink($('a.list-group-item'));
      }).catch(err => {
        $content
          .empty()
          .append($('<section>')
          .append($('<h2 id="status"></h2>').text('Network error ' + err.status))
          .append($('<div id="info"></div>').text(err.statusText)));
      }).finally(() => {
        abortController = null;
      });
    });
  }
}


class DocumentTitle {
  constructor(controller: Controller) {
    controller.bind('setupChanged', (setup: Setup) => {
      const board = setup.board;
      const side = (color: Color) =>
        'K'.repeat(board.pieces(color, 'king').size()) +
        'Q'.repeat(board.pieces(color, 'queen').size()) +
        'R'.repeat(board.pieces(color, 'rook').size()) +
        'B'.repeat(board.pieces(color, 'bishop').size()) +
        'N'.repeat(board.pieces(color, 'knight').size()) +
        'P'.repeat(board.pieces(color, 'pawn').size());
      document.title = side('white') + 'v' + side('black') + ' – Syzygy endgame tablebases';
    });
  }
}


$(() => {
  const controller = new Controller($('#board').attr('data-fen')!);
  const boardView = new BoardView(controller);
  new SideToMoveView(controller);
  new FenInputView(controller);
  new ToolBarView(controller);

  new DocumentTitle(controller);
  new TablebaseView(controller, boardView);
});
