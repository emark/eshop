#!/usr/bin/perl -w

use strict;
use lib "/home/hosting_locumtest/usr/local/lib/perl5";
use Mojolicious::Lite;
use Mojo::UserAgent;
use DBIx::Custom;
use Validator::Custom;
use utf8;
use v5.10.0;

open (DBCONF,"< app.conf") || die "Error open dbconfig file";
my @appconf=<DBCONF>;
close DBCONF;
chomp @appconf;
our $dbi = DBIx::Custom->connect(
			dsn => $appconf[0],
			user => $appconf[1],
			password => $appconf[2],
			option => {mysql_enable_utf8=>1}
);

$dbi->do('SET NAMES utf8');

my $ua = Mojo::UserAgent->new();
my $news = $ua->get("http://club.nastartshop.ru/api/get_recent_posts/")->res->json;

get '/checkout' => sub {
	my $self=shift;
	my $cart=$self->session('cart') || undef;
    my @pid = keys %{$cart};
    my $countpid=@pid || 0;
    $self->stash(
		page_title => 'Ваша корзина',
        page_caption => 'Ваша корзина',
		message => 'К сожалению ваша корзина пока пуста. Оформлять нечего :(',
		news => $news,
	);
    return $self->render('dummy') if $countpid==0 ;
	
	my $pid=' id=';
    $pid=$pid.join(' or id=',@pid); 
    my $result=$dbi->select(
        table => 'products',
        column => [
			'id',
			'title',
			'price',
		],
        where => $pid
    );
    $self->stash(
        cart => $cart,
        products => $result->fetch_hash_all,
		news => $news,
    );
	$self->render('checkout');
};

post '/checkout' => sub {
	my $self = shift;
	my $cart=$self->session('cart');
    my @pid= keys %{$cart};
    my $countpid=@pid || 0;
    $self->stash(
		message => 'Сожалеем, но ваша корзина пока ещё пуста :(',
		page_title => 'Ваша корзина',
        page_caption => 'Ваша корзина',
		news => $news,
	);
    return $self->render('dummy') if $countpid==0 ;

    my $pid=' id=';
    $pid=$pid.join(' or id=',@pid);
    my $result=$dbi->select(
        table => 'products',
        column => [
			'id',
			'title',
			'price',
		],
        where => $pid
    );

	my $vc = Validator::Custom->new;
	my $param = $self->req->params->to_hash;
	my $rule = [
		#person => {message => 'error'} => [
		#	'not_blank'
		#],
		tel => {message => 'error'} => ['not_blank'],
		#email => {message => 'error'} => [
		#	'not_blank',{
		#		'regex' => qr/^.*\@.*\...+/
		#	}
		#],
		delivery_type => ['defined'],
		payment_type => ['defined'],
	];
	my $vresult = $vc->validate($param,$rule);
	if($vresult->is_ok){
		#Generating sign for order
		my $sign = '';
		my $len = 11 + int(rand(10));
		$sign .= chr(48 + rand(74)) for (1..$len);
		$sign =~ s/\W//g;
		#Create order
		$dbi->insert(
			{
				person => $param->{'person'},
				tel => $param->{'tel'},
				email => $param->{'email'},
				address => $param->{'address'},
				delivery => $param->{'delivery_type'},
				payment => $param->{'payment_type'},
				status => 0,
				sysdate => \"NOW()",
				sign => $sign,
			},
			table => 'orders',
		);
		my $order_id = $dbi->select(
							column => 'id',
							table => 'orders',
							where => {sign => $sign},
						)->fetch;
		while(my $ref=$result->fetch_hash){
			$dbi->insert(
				{
					productid => $ref->{'id'},
					title => $ref->{'title'},
					price => $ref->{'price'},
					count => $cart->{$ref->{'id'}},
					orderid => $order_id,
				},
				table => 'items',
			);
		};
		return $self->redirect_to('/thankyou');
	}else{
		$self->stash(
        	cart => $cart,
	        products => $result->fetch_hash_all,
			news => $news,
	    );
		$self->stash(missing => 1) if $vresult->has_missing;
		$self->stash(messages => $vresult->messages_to_hash) if $vresult->has_invalid;
	}
	$self->render('checkout');
};

get '/thankyou' => sub {
	my $self = shift;
	$self->session(expires => 1);#Clearing cart
	$self->stash(
		page_title => 'Спасибо за заказ',
		page_caption => 'Заказ оформлен',
		message=>'Поздравляем! Ваш заказ оформлен. Мы скоро перезвоним вам.',
		news => $news,
	);
	$self->render('dummy');
};

get '/cart' => sub {
    my $self = shift;
    my $cart = $self->session('cart');
	my @pid = keys %{$cart} if $cart;
	my $countpid=@pid || 0;
	$self->stash(
		page_title => 'Ваша корзина',
		page_caption => 'Ваша корзина',
		message => 'Нам очень жаль, но похоже, что ваша корзина пуста :(',
		news => $news,
	);
	return $self->render('dummy') if $countpid == 0;

	my $pid=' id=';
	$pid=$pid.join(' or id=',@pid);	
	my $result=$dbi->select(
		table => 'products',
		column => [
			'id',
			'title',
			'price',
			'url',
			'caturl',
		],
		where => $pid,
	);
    $self->stash(
		cart => $cart,
		products => $result->fetch_hash_all,
	);
    $self->render('cart');
};

post '/cart' => sub{
    my $self=shift;
    my $productid=$self->param('prodid') || 0;
	my $action=$self->param('action');
    my $cart=$self->session('cart');
	if($action eq 'add'){
	    $cart->{$productid}++;
	}elsif($action eq 'remove'){
		$cart->{$productid}-- if $cart->{$productid}>0;
	}
	if($cart->{$productid}==0 || $action eq 'drop'){
		delete $cart->{$productid};
	}
	$self->session(cart => $cart);
	my @pid= keys %{$cart};
	my $countpid=@pid || 0;
	$self->stash(
        page_title => 'Пустая корзина',
        page_caption => 'Ваша корзина',
        message => 'Мы сожалеем, что вам ничего не понравилось, может пройдётесь по другим разделам нашего магазина?',
		news => $news,
    );
    return $self->render('dummy') if $countpid == 0;

	my $pid=' id=';
    $pid=$pid.join(' or id=',@pid);
    my $result=$dbi->select(
        table => 'products',
        column => [
			'id',
			'title',
			'price',
			'caturl',
			'url',
		],
        where => $pid
    );
    $self->stash(
		products => $result->fetch_hash_all,
		cart => $cart,
		news => $news,
	);
    $self->render('cart');
};

get '/catalog' => sub{
	my $self = shift;
	my $catalog = {'url' => 'catalog'};
	my $categories = $dbi->select(
		table => 'pages',
		column => [
			'title',
			'url',
			'description',
		],
		where => {'type' => 0},
	);
	my $price = $dbi->select(
		table => 'products',
		column => [
			'caturl',
			'price',
		],
		where => 'instore >= 0',
	);

	$self->stash(
		catalog => $catalog,
		categories => $categories->fetch_hash_all,
		price => $price->fetch_all,
		news => $news,
	);
	$self->render('categories');
};

get '/catalog/:caturl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $catalog = $dbi->select(
						table => 'pages',
						column => [
							'title',
							'url',
							'description',
						],
						where => {'url' => $caturl},
					);
	my $result = $dbi->select(
		table => 'products',
		column => [
			'title',
			'url',
			'anonse',
			'instore',
			'id',
			'price',
			'image',
		],
		where => {'caturl' => $caturl},
	);
	my $has_content = $catalog->one;
	$self->stash(news => $news);
    return $self->render(status => 404, template =>'not_found') if !$has_content;
	$self->stash(
		product => $result->fetch_hash_all,
		catalog => $has_content,
	);
	$self->render('catalog');
};

get '/catalog/:caturl/:produrl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $produrl = $self->param('produrl');
    my $catalog = $dbi->select(
		table => 'pages',
        column => [
			'title',
			'url'
		],
        where => {'url' => $caturl},
	);
	my $result=$dbi->select(
		table => 'products',
        column => [
			'id',
			'title',
			'price',
			'description',
			'settings',
			'features',
			'image',
			'instore',
			'url',
			'vk_album',
		],
		where => {
			'url' => $produrl,
			'caturl' => $caturl,
		},
	);
	my $has_content = $result->fetch_hash;
	$self->stash(news => $news);
    return $self->render(status => 404, template => 'not_found') if !$has_content;
	$self->stash(
		product => $has_content,
		catalog => $catalog->one,
	);
	$self->render('product');
};

get '/about/:pageurl' => sub{
	my $self=shift;
	my $pageurl = $self->param('pageurl');
	my $result = $dbi->select(
        table => 'pages',
        column => [
			'title',
			'url',
			'description',
			'content',
		],
        where => {'url' => $pageurl},
    );
	my $has_content = $result->one || undef;
	$self->stash(news => $news);
	return $self->render(status => 404, template => 'not_found') if !$has_content;
	$self->stash(
		catalog => $has_content,
	);
	$self->render('page');
};

get '/' => sub{
	my $self = shift;
	my $catalog = {'url' => 'index'};
	my $result = $dbi->select(
        table => 'products',
        column => [
            'title',
            'url',
            'anonse',
            'instore',
            'id',
            'price',
            'image',
			'caturl',
        ],
		where => {'popular' => 1},
    );
	$self->stash(
		news => $news,
		catalog => $catalog,
		products => $result->fetch_hash_all,
	);
	$self->render('index');
};

get '/sitemap' => sub{
	my $self = shift;
	my $pages = $dbi->select(
		table => 'pages',
        column => [
			'url',
			'type',
			'priority',
			'changefreq',
			'lastmod',
		],
	);
	my $products = $dbi->select(
		table => 'products',
		column => [
			'url',
			'caturl',
		],
	);
	$self->stash(
		pages => $pages->fetch_hash_all,
		products => $products->fetch_hash_all,
	);
	$self->render('sitemap');
};

app->secret('ReginaSpector');
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://www.nastartshop.ru/}));
			}
		);
app->start;
