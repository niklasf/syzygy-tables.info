var DEFAULT_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';
var STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';


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
    $('.right-side > .inner')
      .html('<div class="spinner"><div class="double-bounce1"></div><div class="double-bounce2"></div></div>')
      .load('/?fen=' + encodeURIComponent(position.fen()) + '&xhr=1', function (url, status, xhr) {
        if (status == 'error') {
          $('.right-side > .inner').html('<h2 id="status">Network error</h2><div id="info"></div>');
          $('#info').text(xhr.status + ' ' + xhr.statusText);
        } else {
          bindMoveLink($('.list-group-item'));
        }
      });
  });
}


function ApidocLink(controller) {
  controller.bind('positionChanged', function (position) {
    $('#apidoc').attr({
      href: '/apidoc?fen=' + encodeURIComponent(position.fen())
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
  new ApidocLink(controller);

  new DocumentTitle(controller);
  new TablebaseView(controller);
});
