$(function () {
  var board, chess = new Chess('4k3/8/8/8/8/8/8/4K3 w - - 0 1');

  function probe(fen) {
    console.log(fen);
  }

  board = new ChessBoard('board', {
    position: $('#board').attr('data-fen'),
    pieceTheme: '/static/chesspieces/wikipedia/{piece}.png',
    draggable: true,
    dragOffBoard: 'trash',
    sparePieces: true,
    onDrop: function (source, target, piece, newPos, oldPos, orientation) {
      if (source != 'spare' && target != 'trash' && chess.move({ from: source, to: target })) {
        $btn_white.toggleClass('active', chess.turn() == 'w');
        $btn_black.toggleClass('active', chess.turn() == 'b');
        var parts = chess.fen().split(/ /);
        parts[4] = '0';
        parts[5] = '1';
        var fen = parts.join(' ');
        $fen.val(fen);
        probe(fen);
      } else {
        var fen = ChessBoard.objToFen(newPos) + ' ' + ($btn_white.hasClass('active') ? 'w' : 'b') + ' - - 0 1';
        $fen.val(fen);
        chess.load(fen);
        probe(fen);
      }
    }
  });

  var $btn_white = $('#btn-white');
  var $btn_black = $('#btn-black');
  var $fen = $('#fen');

  $btn_white.click(function (event) {
    event.preventDefault();
    var fen = board.fen() + ' w - - 0 1';
    chess.load(fen);
    $fen.val(fen);
    $btn_white.addClass('active');
    $btn_black.removeClass('active');
    probe(fen);
  });

  $btn_black.click(function (event) {
    event.preventDefault();
    var fen = board.fen() + ' b - - 0 1';
    chess.load(fen);
    $fen.val(fen);
    $btn_white.removeClass('active');
    $btn_black.addClass('active');
    probe(fen);
  });

  $('#form-set-fen').submit(function (event) {
    event.preventDefault();

    var parts = $fen.val().trim().split(/\s+/);
    if (parts.length == 1) {
      parts.push($btn_white.hasClass('active') ? 'w' : 'b');
    }
    if (parts.length == 2) {
      parts.push('-');
    }
    if (parts.length == 3) {
      parts.push('-');
    }
    if (parts.length == 4) {
      parts.push('0');
    }
    if (parts.length == 5) {
      parts.push('1');
    }

    var fen = parts.join(' ');
    if (!chess.load(fen)) {
      fen = '4k3/8/8/8/8/8/8/4K3 w - - 0 1';
      chess.load(fen);
    }

    board.position(fen);
    $fen.val(fen);
    probe(fen);
  });
});
