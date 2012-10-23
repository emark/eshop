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

get '/news' => sub{
	my $self = shift;
	my $page = {
		'url' => 'news',
		'type' => 1,
	};
	my $ua = Mojo::UserAgent->new();
	my $news = $ua->get("http://club.nastartshop.ru/api/get_recent_posts/")->res->json;
	
    $self->stash(
		page => $page,
        news => $news,
    );
};

get '/checkout' => sub {
	my $self=shift;
	my $cart=$self->session('cart') || undef;
    my @pid = keys %{$cart};
    my $countpid=@pid || 0;
	my $page = {
		'url' => 'checkout',
		'title' => 'Корзина',
		'content' => 'К сожалению ваша корзина пока пуста. Оформлять нечего :(',
		'type' => 1,
	};
    $self->stash(
		page => $page,
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
    );
	$self->render('checkout');
};

post '/checkout' => sub {
	my $self = shift;
	my $cart=$self->session('cart');
    my @pid= keys %{$cart};
    my $countpid=@pid || 0;
    my $page = {
		'url' => 'checkout',
		'title' => 'Оформление заказа',
		'content' => 'Сожалеем, но ваша корзина пока ещё пуста :(',
		'type' => 1,
	};
	$self->stash(
		page => $page,
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
	    );
		$self->stash(missing => 1) if $vresult->has_missing;
		$self->stash(messages => $vresult->messages_to_hash) if $vresult->has_invalid;
	}
	$self->render('checkout');
};

get '/thankyou' => sub {
	my $self = shift;
	$self->session(expires => 1);#Clearing cart
	my $page = {
		'url' => 'thankyou',
		'title' => 'Заказ оформлен',
		'content' => 'Благодарим за заказ. Мы скоро свяжемся с вами.',
		'type' => 1,
	};
	$self->stash(page => $page);
	$self->render('dummy');
};

get '/cart' => sub {
    my $self = shift;
    my $cart = $self->session('cart');
	my @pid = keys %{$cart} if $cart;
	my $countpid=@pid || 0;
	my $page = {
		'url' => 'cart',
		'title' => 'Корзина',
		'content' => 'В корзине пока ничего нет. Для добавления товаров в корзину, жмите кнопку "Купить" на нужном товаре.',
		'type' => 1,
	};
	$self->stash(
		page => $page,
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
	my $page = {
        'url' => 'cart',
        'title' => 'Корзина',
        'content' => 'Мы сожалеем, что вам ничего не понравилось, может пройдётесь по другим разделам нашего магазина?',
		'type' => 1,
    };
    $self->stash(
        page => $page,
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
	);
    $self->render('cart');
};

get '/catalog' => sub{
	my $self = shift;
	my $page = {
		'url' => 'catalog',
		'type' => 1,
	};
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
			'url',
			'image',
		],
		where => 'instore >= 0',
	);

	$self->stash(
		page => $page,
		categories => $categories->fetch_hash_all,
		price => $price->fetch_all,
	);
	$self->render('catalog');
};

get '/catalog/:caturl' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $page = $dbi->select(
						table => 'pages',
						column => [
							'title',
							'metadescription',
							'url',
							'description',
							'type',
						],
						where => {'url' => $caturl},
					);
	my $result = $dbi->select(
		table => 'products',
		column => [
			'title',
			'url',
			'id',
			'price',
			'image',
		],
		where => {'caturl' => $caturl},
	);
	my $has_content = $page->one;
    return $self->render(status => 404, template =>'not_found') if !$has_content;
	$self->stash(
		product => $result->fetch_hash_all,
		page => $has_content,
	);
	$self->render('category');
};

get '/catalog/:caturl/:produrl.html' => sub {
	my $self = shift;
	my $caturl = $self->param('caturl');
	my $produrl = $self->param('produrl');
    my $category = $dbi->select(
		table => 'pages',
        column => [
			'title',
			'url',
			'metadescription',
			'type',
		],
        where => {'url' => $caturl},
	);
	my $result=$dbi->select(
		table => 'products',
        column => [
			'id',
			'title',
			'metadescription',
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
    return $self->render(status => 404, template => 'not_found') if !$has_content;
	$self->stash(
		product => $has_content,
		page => $category->one,
	);
	$self->render('product');
};

get '/about' => sub{
    my $self = shift;
    my $page = {'url' => 'about'};
    my $pages = $dbi->select(
        table => 'pages',
        column => [
            'title',
            'url',
            'description',
			'type',
        ],
        where => {'type' => 1},
    );

    $self->stash(
		page => $page,
        pages => $pages->fetch_hash_all,
    );
    $self->render('about');
};

get '/' => sub{
	my $self = shift;
	my $page = {
		'url' => 'index',
	};
	my $products = $dbi->select(
        table => 'products',
        column => [
            'title',
            'url',
            'id',
            'price',
            'image',
			'caturl',
        ],
		where => {'popular' => 1},
    );
	$self->stash(
		page => $page,
		products => $products->fetch_hash_all,
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
