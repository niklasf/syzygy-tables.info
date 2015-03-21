var DEFAULT_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';
var STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';


function Controller(fen) {
  var self = this;

  this.events = {};
  this.request = null;
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
          fen = decodeURIComponent(item[1]);
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
      }, null, '/?fen=' + fen);
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

  this.position = position;
  this.trigger('positionChanged', position);

  if (this.request) {
    this.request.abort();
    this.request = null;
  }

  if (this.position.fen() === DEFAULT_FEN) {
    return;
  }

  self.trigger('probeStarted');

  this.request = $.ajax('/api', {
    data: {
      fen: this.position.fen(),
    },
    error: function (xhr, textStatus, errorThrown) {
      if (xhr.status === 0) {
        self.trigger('probeCancelled');
      } else if (xhr.status === 400) {
        self.trigger('probeInvalid');
      } else {
        self.trigger('probeFailed');
      }
    },
    success: function (data) {
      self.trigger('probeFinished', data);
    }
  });
};


function BoardView(controller) {
  var self = this;

  this.fenPart = controller.position.fen().split(/\s+/)[0];

  this.board = new ChessBoard('board', {
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
  });

  controller.bind('positionChanged', function (position) {
    self.setPosition(position);
  });
}

BoardView.prototype.setPosition = function (position) {
  var newFenPart = position.fen().split(/\s+/)[0];
  if (this.fenPart !== newFenPart) {
    this.board.position(newFenPart);
    this.fenPart = newFenPart;
  }
};

BoardView.prototype.flip = function () {
  this.board.flip();
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

  $('#form-set-fen').submit(function (event) {
    event.preventDefault();

    var parts = $('#fen').val().trim().split(/\s+/);
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

    var fen = parts.join(' ');
    var position = new Chess();
    if (!position.load(fen)) {
      controller.push(new Chess(DEFAULT_FEN));
    } else {
      controller.push(new Chess(fen));
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
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', '');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', '');
      })
      .mouseenter(function () {
        var uci = $(this).attr('data-uci');
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', 'inset 0 0 3px 3px yellow');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', 'inset 0 0 3px 3px yellow');
      })
      .mouseleave(function () {
        var uci = $(this).attr('data-uci');
        $('#board .square-' + uci.substr(0, 2)).css('box-shadow', '');
        $('#board .square-' + uci.substr(2, 2)).css('box-shadow', '');
      });
  }

  bindMoveLink($('.list-group-item'));

  controller.bind('positionChanged', function (position) {
    $('#winning')
      .empty()
      .toggleClass('white-turn', position.turn() === 'w')
      .toggleClass('black-turn', position.turn() === 'b');

    $('#drawing').empty();

    $('#losing')
      .empty()
      .toggleClass('white-turn', position.turn() === 'w')
      .toggleClass('black-turn', position.turn() === 'b');

    $('#info').empty();

    var fen = position.fen();

    if (fen === DEFAULT_FEN) {
      $('#status').text('Draw by insufficient material').removeClass('black-win').removeClass('white-win');
      $('#info').html('<p>Syzygy tablebases provide win-draw-loss and distance-to-zero information for all endgame positions with up to 6 pieces.</p><p>Minmaxing the DTZ values guarantees winning all winning positions and defending all drawn positions.</p><p><strong>Setup a position on the board to probe the tablebases.</strong></p><p>Sample positions:</p><ul><li><a href="/?fen=6N1/5KR1/2n5/8/8/8/2n5/1k6%20w%20-%20-%200%201">The longest six piece endgame</a></li><li><a href="/?fen=4r3/1K6/8/8/5p2/3k4/8/7Q%20b%20-%20-%200%201">Black is just about saved by the fifty-move rule in this KQvKRP endgame</a></li></ul><h2>Contact</h2><p>Feedback <a href="/legal">via mail</a>, bug reports and <a href="https://github.com/niklasf/syzygy-tables.info">pull requests</a> are welcome.</p>');
    } else if (fen === STARTING_FEN) {
      $('#status').text('Position not found in tablebases').removeClass('black-win').removeClass('white-win');
      $('#info').html('<p><a href="https://en.wikipedia.org/wiki/Solving_chess">Chess is not yet solved.</a></p>');
    } else if (position.in_checkmate()) {
      if (position.turn() === 'b') {
        $('#status').text('White won by checkmate').removeClass('black-win').addClass('white-win');
      } else {
        $('#status').text('Black won by checkmate').removeClass('white-win').addClass('black-win');
      }
    } else if (position.in_stalemate()) {
      $('#status').text('Draw by stalemate').removeClass('black-win').removeClass('white-win');
    } else if (position.insufficient_material()) {
      $('#status').text('Draw by insufficient material').removeClass('black-win').removeClass('white-win');
      $('#info').html('<p><strong>The game is drawn</strong> because with the remaining material no sequence of legal moves can lead to a checkmate.</p>');
    }
  });

  controller.bind('probeStarted', function() {
    $('#info').append('<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>');
  });

  controller.bind('probeInvalid', function() {
    $('#status').text('Invalid position').removeClass('black-win').removeClass('white-win');
    $('#info').html('<p>The given position is not a legal chess position.</p>');
  });

  controller.bind('probeCancelled', function () {
    $('#status').text('Request cancelled');
    $('#info').empty();
  });

  controller.bind('probeFailed', function (status, textStatus) {
    $('#status').text('Network error').removeClass('black-win').removeClass('white-win');
    $('#info')
      .text('Request failed: ' + textStatus)
      .append('<div class="reload"><a class="btn btn-default" href="/?fen=' + encodeURIComponent(controller.position.fen()) + '">Try again</a></div>');
  });

  controller.bind('probeFinished', function (data) {
    $('#info').children('.spinner').remove();

    if (controller.position.in_checkmate() || controller.position.in_stalemate()) {
      // No moves need to be displayed.
      return;
    }

    if (data.wdl === null) {
      $('#status').text('Position not found in tablebases').removeClass('black-win').removeClass('white-win');
      if (controller.position.fen() !== STARTING_FEN) {
        $('#info').empty();
      }
      $('#info').append('<p>Syzygy tables only provide information for positions with up to 6 pieces and no castling rights.</p>');
    } else if (data.dtz === 0) {
      // A draw by insufficient material would be already stated. Otherwise
      // declare the tablebase draw.
      if (!controller.position.insufficient_material()) {
        $('#status').text('Tablebase draw').removeClass('black-win').removeClass('white-win');
        $('#info').empty();
      }
    } else if (controller.position.turn() === 'w') {
      if (data.dtz > 0) {
        $('#status').text('White is winning with DTZ ' + data.dtz).removeClass('black-win').addClass('white-win');
      } else {
        $('#status').text('White is losing with DTZ ' + Math.abs(data.dtz)).removeClass('white-win').addClass('black-win');
      }
      $('#info').empty();
    } else {
      if (data.dtz > 0) {
        $('#status').text('Black is winning with DTZ ' + data.dtz).removeClass('white-win').addClass('black-win');
      } else {
        $('#status').text('Black is losing with DTZ ' + Math.abs(data.dtz)).removeClass('black-win').addClass('white-win');
      }
      $('#info').empty();
    }

    if (data.wdl === -1) {
      $('#info').html('<p><strong>This is a blessed loss.</strong> Mate can be forced, but a draw can be achieved under the fifty-move rule.</p>');
    } else if (data.wdl === 1) {
      $('#info').html('<p><strong>This is a cursed win.</strong> Mate can be forced, but a draw can be achieved under the fifty-move rule.</p>');
    }

    var moves = [];
    var tmpChess = new Chess(controller.position.fen());
    for (var uci in data.moves) {
      if (data.moves.hasOwnProperty(uci)) {
        var moveInfo;
        if (uci.length == 5) {
          moveInfo = tmpChess.move({
            from: uci.substr(0, 2),
            to: uci.substr(2, 2),
            promotion: uci[4]
          });
        } else {
          moveInfo = tmpChess.move({
            from: uci.substr(0, 2),
            to: uci.substr(2, 2)
          });
        }

        var checkmate = tmpChess.in_checkmate();
        var stalemate = tmpChess.in_stalemate();
        var insufficient_material = tmpChess.insufficient_material();
        var dtz = data.moves[uci];

        var moveFen = tmpChess.fen();
        var parts = moveFen.split(/ /);
        var halfMoves = parseInt(parts[4], 10);
        parts[4] = '0';
        parts[5] = '1';
        moveFen = parts.join(' ');

        moves.push({
          uci: uci,
          san: moveInfo.san,
          checkmate: checkmate,
          stalemate: stalemate,
          insufficient_material: insufficient_material,
          dtz: dtz,
          winning: (dtz !== null && dtz < 0) || checkmate,
          drawing: stalemate || insufficient_material || (dtz === 0 || (dtz === null && data.wdl !== null && data.wdl < 0)),
          zeroing: halfMoves === 0,
          fen: moveFen
        });

        tmpChess.undo();
      }
    }

    moves.sort(function (a, b) {
      // Compare by definite win.
      if (a.checkmate && !b.checkmate) {
        return -1;
      } else if (!a.checkmate && b.checkmate) {
        return 1;
      }

      // Compare by stalemate.
      if (a.stalemate && !b.stalemate) {
        return -1;
      } else if (!a.stalemate && b.stalemate) {
        return 1;
      }

      // Compare by insufficient material.
      if (a.insufficient_material && !b.insufficient_material) {
        return -1;
      } else if (!a.insufficient_material && b.insufficient_material) {
        return 1;
      }

      // Compare by zeroing.
      if (a.dtz < 0 && b.dtz < 0 && a.zeroing && !b.zeroing) {
        return -1;
      } else if (a.dtz < 0 && b.dtz < 0 && !a.zeroing && b.zeroing) {
        return 1;
      }

      // Compare by DTZ.
      if (a.dtz < b.dtz || (a.dtz === null && b.dtz !== null)) {
        return 1;
      } else if (a.dtz > b.dtz || (a.dtz !== null && b.dtz === null)) {
        return -1;
      }

      // Compare by UCI notation.
      if (a.uci < b.uci) {
        return -1;
      } else if (a.uci > b.uci) {
        return 1;
      } else {
        return 0;
      }
    });

    for (var i = 0; i < moves.length; i++) {
      var move = moves[i];

      var badge = 'Unknown';
      if (move.checkmate) {
        badge = 'Checkmate';
      } else if (move.stalemate) {
        badge = 'Stalemate';
      } else if (move.insufficient_material) {
        badge = 'Insufficient material';
      } else if (move.dtz === 0) {
        badge = 'Draw';
      } else if (move.dtz !== null) {
        if (move.zeroing && move.dtz < 0) {
          badge = 'Zeroing';
        } else if (move.dtz < 0) {
          badge = 'Win with DTZ ' + Math.abs(move.dtz);
        } else {
          badge = 'Loss with DTZ ' + move.dtz;
        }
      }

      var moveLink = $('<a class="list-group-item"></a>')
        .attr({
          'data-uci': move.uci,
          'data-fen': move.fen,
          'href': '/?fen=' + encodeURIComponent(move.fen)
        })
        .append(move.san)
        .append(' ')
        .append($('<span class="badge"></span>').text(badge));

      bindMoveLink(moveLink);

      if (move.winning) {
        moveLink.appendTo('#winning');
      } else if (move.drawing) {
        moveLink.appendTo('#drawing');
      } else {
        moveLink.appendTo('#losing');
      }
    }
  });
}


function ApidocLink(controller) {
  controller.bind('positionChanged', function (position) {
    $('#apidoc').attr({
      href: '/apidoc?fen=' + encodeURIComponent(position.fen())
    });
  });
}


$(function () {
  var controller = new Controller($('#board').attr('data-fen'));
  var boardView = new BoardView(controller);
  new SideToMoveView(controller);
  new FenInputView(controller);
  new ToolBarView(controller, boardView);
  new ApidocLink(controller);

  new TablebaseView(controller);
});
