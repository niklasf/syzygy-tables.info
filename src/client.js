/**
 * This file is part of the syzygy-tables.info tablebase probing website.
 * Copyright (C) 2015-2018 Niklas Fiekas <niklas.fiekas@backscattering.de>
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

var $ = require('jquery');
var Chess = require('chess.js').Chess;
var Chessground = require('chessground').Chessground;


var DEFAULT_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';


function strRepeat(str, num) {
  var r = '';
  for (var i = 0; i < num; i++) {
    r += str;
  }
  return r;
}


function strCount(haystack, needle) {
  return haystack.split(needle).length - 1;
}


function Controller(fen) {
  var self = this;

  this.events = {};
  this.position = new Chess(fen || DEFAULT_FEN);

  window.addEventListener('popstate', function (event) {
    var fen = DEFAULT_FEN;

    if (event.state && event.state.fen) {
      fen = event.state.fen;
    } else {
      // Extract the FEN from the query string.
      var query = location.search.substr(1);
      query.split('&').forEach(function (part) {
        var item = part.split('=');
        if (item[0] == 'fen') {
          fen = decodeURIComponent(item[1]).replace(/_/g, ' ');
        }
      });
    }

    self.setPosition(new Chess(fen));
  });
}

Controller.prototype.bind = function (event, cb) {
  this.events[event] = this.events[event] || [];
  this.events[event].push(cb);
};

Controller.prototype.trigger = function (event) {
  var self = this;
  if (!this.events[event]) {
    return;
  }

  var args = arguments;
  this.events[event].forEach(function (cb) {
    cb.apply(self, Array.prototype.slice.call(args, 1));
  });
};

Controller.prototype.push = function (position) {
  var fenParts = position.fen().split(/\s+/);
  fenParts[4] = '0';
  fenParts[5] = '1';
  var fen = fenParts.join(' ');

  if (this.position.fen() != fen) {
    if ('pushState' in history) {
      history.pushState({
        fen: fen
      }, null, '/?fen=' + fen.replace(/\s/g, '_'));
    }

    this.setPosition(new Chess(fen));
  }
};

Controller.prototype.pushMove = function (from, to) {
  var tmpBoard = new Chess(this.position.fen());
  var legalMoves = tmpBoard.moves({ verbose: true });

  for (var i = 0; i < legalMoves.length; i++) {
    var legalMove = legalMoves[i];
    if (!legalMove.promotion && legalMove.from === from && legalMove.to === to) {
      tmpBoard.move(legalMove);
      this.push(tmpBoard);
      return true;
    }
  }

  return false;
};

Controller.prototype.setPosition = function (position) {
  var self = this;

  if (this.position.fen() != position.fen()) {
    this.position = position;
    this.trigger('positionChanged', position);
  }
};


function BoardView(controller) {
  var self = this;

  this.ground = Chessground(document.getElementById('board'), {
    fen: controller.position.fen(),
    autoCastle: false,
    events: {
      move: function (orig, dest) {
        // If the change is a legal move, play it.
        if (controller.pushMove(orig, dest)) return;

        // Otherwise just change to position.
        var fenParts = controller.position.fen().split(/\s+/);
        fenParts[0] = self.fenPart = self.ground.getFen();
        controller.push(new Chess(fenParts.join(' ')));
      }
    }
  });
  /* XXX this.board = new ChessBoard('board', {
    position: self.fenPart,
    pieceTheme: '/static/pieces/{piece}.svg',
    draggable: true,
    dropOffBoard: 'trash',
    sparePieces: true,
    onDrop: function (from, to, piece, newPos, oldPos, orientation) {
      self.fenPart = ChessBoard.objToFen(newPos);

      // If the change is a legal move, do it.
      if (from != 'spare' && to != 'trash') {
        if (controller.pushMove(from, to)) {
          return;
        }
      }

      // Otherwise just change to position.
      var fenParts = controller.position.fen().split(/\s+/);
      fenParts[0] = ChessBoard.objToFen(newPos);
      controller.push(new Chess(fenParts.join(' ')));
    }
  }); */

  controller.bind('positionChanged', function (position) {
    self.setPosition(position);
  });
}

BoardView.prototype.setPosition = function (position) {
  this.ground.set({
    fen: position.fen()
  });
};

BoardView.prototype.flip = function () {
  this.ground.toggleOrientation();
};


function SideToMoveView(controller) {
  var self = this;

  $('#btn-white').click(function (event) {
    event.preventDefault();
    var fenParts = controller.position.fen().split(/\s+/);
    fenParts[1] = 'w';
    controller.push(new Chess(fenParts.join(' ')));
  });

  $('#btn-black').click(function (event) {
    event.preventDefault();
    var fenParts = controller.position.fen().split(/\s+/);
    fenParts[1] = 'b';
    controller.push(new Chess(fenParts.join(' ')));
  });

  this.setPosition(controller.position);
  controller.bind('positionChanged', function (position) {
    self.setPosition(position);
  });
}

SideToMoveView.prototype.setPosition = function (position) {
  $('#btn-white').toggleClass('active', position.turn() === 'w');
  $('#btn-black').toggleClass('active', position.turn() === 'b');
};


function FenInputView(controller) {
  var self = this;

  function parseFen(fen) {
    var parts = fen.trim().split(/\s+/);
    if (parts[0] === '') {
      parts[0] = DEFAULT_FEN.split(/\s+/)[0];
    }
    if (parts.length === 1) {
      parts.push(controller.position.turn());
    }
    if (parts.length === 2) {
      parts.push('-');
    }
    if (parts.length === 3) {
      parts.push('-');
    }
    if (parts.length === 4) {
      parts.push('0');
    }
    if (parts.length === 5) {
      parts.push('1');
    }

    var position = new Chess();
    if (position.load(parts.join(' '))) {
      return position;
    }
  }

  var input = document.getElementById('fen');
  if (input.setCustomValidity) {
    input.oninput = input.onchange = function() {
      if (parseFen(input.value)) {
        input.setCustomValidity('');
      } else {
        input.setCustomValidity('Invalid FEN');
      }
    };
  }

  $('#form-set-fen').submit(function (event) {
    event.preventDefault();

    var position = parseFen(input.value);
    if (position) {
      controller.push(position);
    } else {
      input.focus();
    }
  });

  this.setPosition(controller.position);
  controller.bind('positionChanged', function (position) {
    self.setPosition(position);
  });
}

FenInputView.prototype.setPosition = function (position) {
  var fen = position.fen();
  if (fen === DEFAULT_FEN) {
    $('#fen').val('');
  } else {
    $('#fen').val(fen);
  }
};


function ToolBarView(controller, boardView) {
  $('#btn-flip-board').click(function (event) {
    boardView.flip();
  });

  $('#btn-clear-board').click(function (event) {
    event.preventDefault();

    var parts = controller.position.fen().split(/\s+/);
    var defaultParts = DEFAULT_FEN.split(/\s+/);
    var fen = defaultParts[0] + ' ' + parts[1] + ' - - 0 1';

    controller.push(new Chess(fen));
  });

  $('#btn-swap-colors').click(function (event) {
    event.preventDefault();

    var parts = controller.position.fen().split(/\s+/);

    var fenPart = '';
    for (var i = 0; i < parts[0].length; i++) {
      if (parts[0][i] === parts[0][i].toLowerCase()) {
        fenPart += parts[0][i].toUpperCase();
      } else {
        fenPart += parts[0][i].toLowerCase();
      }
    }
    parts[0] = fenPart;

    parts[2] = '-';
    parts[3] = '-';

    controller.push(new Chess(parts.join(' ')));
  });

  $('#btn-mirror-horizontal').click(function (event) {
    event.preventDefault();

    var parts = controller.position.fen().split(/\s+/);
    var positionParts = parts[0].split(/\//);
    for (var i = 0; i < positionParts.length; i++) {
      positionParts[i] = positionParts[i].split('').reverse().join('');
    }

    var fen = positionParts.join('/') + ' ' + parts[1] + ' - - 0 1';
    controller.push(new Chess(fen));
  });

  $('#btn-mirror-vertical').click(function (event) {
    event.preventDefault();

    var parts = controller.position.fen().split(/\s+/);
    var positionParts = parts[0].split(/\//);
    positionParts.reverse();

    var fen = positionParts.join('/') + ' '+ parts[1] + ' - - 0 1';
    controller.push(new Chess(fen));
  });
}


function TablebaseView(controller) {
  function bindMoveLink(moveLink) {
    moveLink
      .click(function (event) {
        event.preventDefault();
        var fen = $(this).attr('data-fen');
        var uci = $(this).attr('data-uci');
        controller.push(new Chess(fen));
        // XXX
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', '');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', '');
      })
      .mouseenter(function () {
        // XXX
        var uci = $(this).attr('data-uci');
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', 'inset 0 0 3px 3px yellow');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', 'inset 0 0 3px 3px yellow');
      })
      .mouseleave(function () {
        // XXX
        var uci = $(this).attr('data-uci');
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', '');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', '');
      });
  }

  bindMoveLink($('.list-group-item'));

  controller.bind('positionChanged', function (position) {
    $('.right-side > .inner')
      .html('<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>')
      .load('/?fen=' + encodeURIComponent(position.fen()) + '&xhr=probe', function (url, status, xhr) {
        if (status == 'error') {
          $('.right-side > .inner')
            .empty()
            .append(
              $('<section>')
                .append($('<h2 id="status"></h2>').text('Network error ' + xhr.status))
                .append($('<div id="info"></div>').text(xhr.statusText)));
        } else {
          bindMoveLink($('.list-group-item'));
        }
      });
  });
}


function DocumentTitle(controller) {
  controller.bind('positionChanged', function (position) {
    var fen = position.fen().split(/\s/)[0];

    document.title = (
      strRepeat('K', strCount(fen, 'K')) +
      strRepeat('Q', strCount(fen, 'Q')) +
      strRepeat('R', strCount(fen, 'R')) +
      strRepeat('B', strCount(fen, 'B')) +
      strRepeat('N', strCount(fen, 'N')) +
      strRepeat('P', strCount(fen, 'P')) +
      'v' +
      strRepeat('K', strCount(fen, 'k')) +
      strRepeat('Q', strCount(fen, 'q')) +
      strRepeat('R', strCount(fen, 'r')) +
      strRepeat('B', strCount(fen, 'b')) +
      strRepeat('N', strCount(fen, 'n')) +
      strRepeat('P', strCount(fen, 'p')) +
      ' – Syzygy endgame tablebases');
  });
}


$(function () {
  var controller = new Controller($('#board').attr('data-fen'));
  var boardView = new BoardView(controller);
  new SideToMoveView(controller);
  new FenInputView(controller);
  new ToolBarView(controller, boardView);

  new DocumentTitle(controller);
  new TablebaseView(controller);
});
